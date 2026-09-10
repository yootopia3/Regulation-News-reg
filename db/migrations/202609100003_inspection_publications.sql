begin;
alter table public.sanction_inspections add column review_revision integer not null default 0;
alter table public.sanction_inspections add column review_draft jsonb;
create table public.sanction_publications (
 inspection_id uuid primary key references public.sanction_inspections(id) on delete cascade,
 article_id uuid not null references public.articles(id) on delete cascade,
 revision integer not null,
 status text not null check(status in ('published','withdrawn')),
 report jsonb,
 published_at timestamptz,
 check(status<>'published' or report is not null)
);
create table public.inspection_review_events (
 id bigint generated always as identity primary key,
 inspection_id uuid not null references public.sanction_inspections(id) on delete cascade,
 actor uuid, action text not null, revision integer not null,
 created_at timestamptz not null default now()
);
alter table public.sanction_publications enable row level security;
alter table public.inspection_review_events enable row level security;
revoke all on public.sanction_publications,public.inspection_review_events from public,anon,authenticated;
grant all on public.sanction_publications,public.inspection_review_events to service_role;
grant usage,select on sequence public.inspection_review_events_id_seq to service_role;

create function public.inspection_review_reset() returns trigger language plpgsql
set search_path=public,pg_temp as $$
begin
 if new.result is distinct from old.result or new.request_id is distinct from old.request_id
 or new.versions is distinct from old.versions or new.status is distinct from old.status then
  new.review_draft := null;
  new.review_revision := old.review_revision+1;
 end if;
 return new;
end $$;
create trigger inspection_review_reset before update on public.sanction_inspections
for each row execute function public.inspection_review_reset();

create function public.inspection_publication_reset() returns trigger language plpgsql
set search_path=public,pg_temp as $$
begin
 if new.review_revision is distinct from old.review_revision then
  update sanction_publications set status='withdrawn',report=null where inspection_id=new.id and status='published';
  if found then insert into inspection_review_events(inspection_id,action,revision)
    values(new.id,'automatic_withdrawal',new.review_revision); end if;
 end if;
 return null;
end $$;
create trigger inspection_publication_reset after update on public.sanction_inspections
for each row execute function public.inspection_publication_reset();

create function public.inspection_review_action(p_id uuid,p_actor uuid,p_revision integer,p_action text,p_report jsonb default null)
returns integer language plpgsql set search_path=public,pg_temp as $$
declare job sanction_inspections; rev integer;
begin
 perform pg_advisory_xact_lock(20260910);
 select * into job from sanction_inspections where id=p_id for update;
 if not found or job.review_revision<>p_revision then raise exception 'review_conflict'; end if;
 if p_action not in ('save','publish','withdraw') then raise exception 'invalid_action'; end if;
 if p_action<>'withdraw' and (job.status<>'needs_review' or job.versions is distinct from inspection_versions())
 then raise exception 'review_conflict'; end if;
 if p_action='save' and (p_report is null or jsonb_typeof(p_report)<>'object') then raise exception 'invalid_report'; end if;
 if p_action='publish' and job.review_draft is null then raise exception 'review_required'; end if;
 update sanction_inspections set review_revision=review_revision+1,
 review_draft=case when p_action='save' then p_report else review_draft end
 where id=p_id returning review_revision into rev;
 if p_action='publish' then
  insert into sanction_publications(inspection_id,article_id,revision,status,report,published_at)
  values(p_id,job.article_id,rev,'published',job.review_draft,now()) on conflict(inspection_id) do update
  set revision=rev,status='published',report=job.review_draft,published_at=now();
 end if;
 insert into inspection_review_events(inspection_id,actor,action,revision) values(p_id,p_actor,p_action,rev);
 return rev;
end $$;
revoke all on function public.inspection_review_reset(),public.inspection_publication_reset(),public.inspection_review_action(uuid,uuid,integer,text,jsonb) from public,anon,authenticated;
grant execute on function public.inspection_review_reset(),public.inspection_publication_reset(),public.inspection_review_action(uuid,uuid,integer,text,jsonb) to service_role;
commit;
