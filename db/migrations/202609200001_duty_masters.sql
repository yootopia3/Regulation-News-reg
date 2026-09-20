-- Register a reviewed-for-use inference master separately from approved allocations.
-- Migration alone preserves the current organization basis and publications.
begin;
select pg_advisory_xact_lock(20260910);
create table public.inspection_duty_masters (
 id uuid primary key default gen_random_uuid(),
 revision integer not null default 1 check(revision=1),
 version text not null check(length(version) between 1 and 80),
 fingerprint text not null unique check(fingerprint ~ '^[0-9a-f]{64}$'),
 payload jsonb not null check(coalesce(jsonb_typeof(payload)='object' and payload->>'scope'='headquarters_only'
   and payload->>'version'=version and jsonb_typeof(payload->'duties')='array'
   and jsonb_array_length(payload->'duties') between 1 and 1000,false)),
 active boolean not null default false,
 created_at timestamptz not null default now()
);
create unique index inspection_one_active_master on public.inspection_duty_masters(active) where active;
alter table public.inspection_duty_masters enable row level security;
revoke all on public.inspection_duty_masters from public,anon,authenticated;
grant select,insert,update on public.inspection_duty_masters to service_role;

create function public.inspection_master_immutable() returns trigger language plpgsql
set search_path=public,pg_temp as $$
begin
 if new.id is distinct from old.id or new.revision is distinct from old.revision
 or new.version is distinct from old.version or new.fingerprint is distinct from old.fingerprint
 or new.payload is distinct from old.payload then raise exception 'immutable_master'; end if;
 return new;
end $$;
create trigger inspection_master_immutable before update on public.inspection_duty_masters
for each row execute function public.inspection_master_immutable();

create or replace function public.inspection_versions() returns jsonb language sql stable
set search_path=public,pg_temp as $$
 select coalesce(
   (select jsonb_object_agg(id::text,revision) from inspection_duty_masters where active),
   (select jsonb_object_agg(id::text,revision) from internal_documents where status='active' and document_kind='organization'),
   '{}'::jsonb);
$$;
create trigger inspection_master_changed after insert or update or delete on public.inspection_duty_masters
for each statement execute function public.inspection_invalidate();

create function public.inspection_master_activate(p_id uuid) returns void language plpgsql
set search_path=public,pg_temp as $$
begin
 perform pg_advisory_xact_lock(20260910);
 if not exists(select 1 from inspection_duty_masters where id=p_id) then raise exception 'master_not_found'; end if;
 if exists(select 1 from inspection_duty_masters where id=p_id and active) then return; end if;
 update inspection_duty_masters set active=false where active;
 update inspection_duty_masters set active=true where id=p_id;
end $$;
revoke all on function public.inspection_master_immutable(),public.inspection_master_activate(uuid) from public,anon,authenticated;
grant execute on function public.inspection_master_immutable(),public.inspection_master_activate(uuid) to service_role;
commit;
