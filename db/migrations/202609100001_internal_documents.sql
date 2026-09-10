-- Stage A only. Apply to the confirmed project before enabling the feature.
begin;

create table public.internal_documents (
    id uuid primary key,
    title text not null check (length(title) between 1 and 120),
    document_kind text not null check (document_kind in ('allocation','analysis')),
    effective_date date not null,
    sha256 text not null check (sha256 ~ '^[a-f0-9]{64}$'),
    object_key text not null unique,
    status text not null default 'uploading' check (status in ('uploading','queued','processing','review','active','retired','failed','deleting','delete_failed','deleted')),
    revision integer not null default 0,
    warnings jsonb not null default '[]',
    warnings_acknowledged boolean not null default false,
    error_code text,
    created_by uuid not null,
    created_at timestamptz not null default now()
);
create unique index internal_documents_one_active on public.internal_documents(document_kind) where status='active';
create unique index internal_documents_live_hash on public.internal_documents(sha256) where status<>'deleted';
create table public.internal_document_units (
    document_id uuid not null references public.internal_documents(id) on delete cascade,
    article_key text not null,
    heading text not null,
    department text not null default '',
    body text not null,
    start_paragraph integer not null,
    end_paragraph integer not null,
    reviewed boolean not null default false,
    primary key (document_id, article_key)
);
create table public.internal_document_jobs (
    document_id uuid primary key references public.internal_documents(id) on delete cascade,
    kind text not null check(kind in ('extract','delete')),
    attempts integer not null default 0,
    lease_token uuid,
    lease_until timestamptz,
    available_at timestamptz not null default now()
);
create table public.internal_document_events (
    id bigint generated always as identity primary key,
    document_id uuid not null references public.internal_documents(id),
    actor uuid,
    action text not null,
    created_at timestamptz not null default now()
);
create table public.internal_admin_limits (
    key text primary key,
    hits integer not null,
    expires_at timestamptz not null
);
alter table public.internal_admin_limits enable row level security;
revoke all on public.internal_admin_limits from public,anon,authenticated;
grant all on public.internal_admin_limits to service_role;
create function public.internal_admin_rate_limit(p_key text,p_limit integer,p_seconds integer) returns boolean
language plpgsql security invoker set search_path=public,pg_temp as $$
declare count_now integer;
begin
    delete from internal_admin_limits where expires_at < now()-interval '1 hour';
    insert into internal_admin_limits(key,hits,expires_at) values(p_key,1,now()+make_interval(secs=>p_seconds))
    on conflict(key) do update set
      hits=case when internal_admin_limits.expires_at<=now() then 1 else internal_admin_limits.hits+1 end,
      expires_at=case when internal_admin_limits.expires_at<=now() then now()+make_interval(secs=>p_seconds) else internal_admin_limits.expires_at end
    returning hits into count_now;
    return count_now<=p_limit;
end $$;

alter table public.internal_documents enable row level security;
alter table public.internal_document_units enable row level security;
alter table public.internal_document_jobs enable row level security;
alter table public.internal_document_events enable row level security;
revoke all on public.internal_documents, public.internal_document_units, public.internal_document_jobs, public.internal_document_events from public, anon, authenticated;
grant all on public.internal_documents, public.internal_document_units, public.internal_document_jobs, public.internal_document_events to service_role;
grant usage, select on sequence public.internal_document_events_id_seq to service_role;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('internal-documents','internal-documents',false,2097152,array['application/octet-stream'])
on conflict(id) do update set public=false,file_size_limit=2097152,allowed_mime_types=array['application/octet-stream'];
-- RESTRICTIVE protects this bucket even if another bucket has a broad permissive policy.
create policy internal_documents_deny_clients on storage.objects as restrictive
for all to anon, authenticated
using(bucket_id <> 'internal-documents') with check(bucket_id <> 'internal-documents');

create function public.internal_document_enqueue(p_id uuid,p_actor uuid) returns void
language plpgsql security invoker set search_path=public,pg_temp as $$
begin
    perform pg_advisory_xact_lock(20260910);
    update internal_documents set status='queued',revision=revision+1
      where id=p_id and status='uploading';
    if not found then raise exception 'state_conflict'; end if;
    insert into internal_document_jobs(document_id,kind) values(p_id,'extract');
    insert into internal_document_events(document_id,actor,action) values(p_id,p_actor,'uploaded');
end $$;

create function public.internal_document_action(p_id uuid,p_actor uuid,p_input jsonb) returns integer
language plpgsql security invoker set search_path=public,pg_temp as $$
declare d internal_documents; u jsonb; requested text := p_input->>'action'; result integer;
begin
    -- Serializes activations across documents as well as competing edits.
    perform pg_advisory_xact_lock(20260910);
    select * into d from internal_documents where id=p_id for update;
    if not found or d.revision <> (p_input->>'revision')::integer then raise exception 'state_conflict'; end if;
    if requested='review' then
        if d.status <> 'review' then raise exception 'state_conflict'; end if;
        for u in select value from jsonb_array_elements(p_input->'units') loop
            update internal_document_units set department=u->>'department',reviewed=(u->>'reviewed')::boolean
              where document_id=p_id and article_key=u->>'article_key';
            if not found then raise exception 'state_conflict'; end if;
        end loop;
        update internal_documents set warnings_acknowledged=(p_input->>'warnings_acknowledged')::boolean where id=p_id;
    elsif requested='activate' then
        if d.status <> 'review' or not d.warnings_acknowledged or d.effective_date > (now() at time zone 'Asia/Seoul')::date
          or not exists(select 1 from internal_document_units where document_id=p_id)
          or exists(select 1 from internal_document_units where document_id=p_id and not reviewed)
          then raise exception 'state_conflict'; end if;
        insert into internal_document_events(document_id,actor,action)
          select id,p_actor,'retired' from internal_documents where document_kind=d.document_kind and status='active';
        update internal_documents set status='retired',revision=revision+1 where document_kind=d.document_kind and status='active';
        update internal_documents set status='active' where id=p_id;
    elsif requested='retry' then
        if d.status <> 'failed' then raise exception 'state_conflict'; end if;
        update internal_documents set status='queued',error_code=null where id=p_id;
        insert into internal_document_jobs(document_id,kind) values(p_id,'extract')
          on conflict(document_id) do update set kind='extract',attempts=0,lease_token=null,lease_until=null,available_at=now();
    elsif requested='delete' then
        if d.status in ('deleted','deleting','processing') then raise exception 'state_conflict'; end if;
        -- Upload API has a 60s deadline and 20s storage timeout. Leave a grace period
        -- before cleaning up a crashed upload; never delete an in-flight upload.
        if d.status='uploading' and d.created_at>now()-interval '15 minutes' then raise exception 'state_conflict'; end if;
        update internal_documents set status='deleting',error_code=null where id=p_id;
        insert into internal_document_jobs(document_id,kind) values(p_id,'delete')
          on conflict(document_id) do update set kind='delete',attempts=0,lease_token=null,lease_until=null,available_at=now();
    else raise exception 'state_conflict'; end if;
    update internal_documents set revision=revision+1 where id=p_id returning revision into result;
    insert into internal_document_events(document_id,actor,action) values(p_id,p_actor,requested);
    return result;
end $$;

create function public.internal_document_claim() returns jsonb
language plpgsql security invoker set search_path=public,pg_temp as $$
declare j internal_document_jobs; d internal_documents; token uuid := gen_random_uuid();
begin
    perform pg_advisory_xact_lock(20260910);
    -- A worker crash does not leave an unbounded lease or infinite retry loop.
    update internal_documents set status=case when status='deleting' then 'delete_failed' else 'failed' end,error_code='worker_exhausted',revision=revision+1
      where id in (select document_id from internal_document_jobs where attempts>=3 and lease_until<now()) and error_code is distinct from 'worker_exhausted';
    select * into j from internal_document_jobs where available_at<=now() and attempts<3
      and (lease_until is null or lease_until<now()) order by available_at for update skip locked limit 1;
    if not found then return null; end if;
    update internal_document_jobs set lease_token=token,lease_until=now()+interval '5 minutes',attempts=attempts+1 where document_id=j.document_id;
    update internal_documents set status=case when j.kind='delete' then 'deleting' else 'processing' end,revision=revision+1
      where id=j.document_id returning * into d;
    return jsonb_build_object('document_id',d.id,'object_key',d.object_key,'sha256',d.sha256,'kind',j.kind,'lease_token',token);
end $$;

create function public.internal_document_finish(p_id uuid,p_token uuid,p_units jsonb,p_warnings jsonb,p_error text) returns void
language plpgsql security invoker set search_path=public,pg_temp as $$
declare j internal_document_jobs; u jsonb;
begin
    perform pg_advisory_xact_lock(20260910);
    select * into j from internal_document_jobs where document_id=p_id and lease_token=p_token for update;
    if not found or j.lease_until < now() then raise exception 'stale_lease'; end if;
    if p_error is not null then
        if p_error not in ('invalid_hwp','encrypted_hwp','unsupported_hwp','document_limit','parser_failed','parser_timeout','storage_failed','worker_failed') then p_error:='worker_failed'; end if;
        update internal_documents set status=case when j.kind='delete' then case when j.attempts>=3 then 'delete_failed' else 'deleting' end else 'failed' end,error_code=p_error,revision=revision+1 where id=p_id;
        update internal_document_jobs set available_at=now()+interval '1 minute',lease_until=null,lease_token=null where document_id=p_id;
        if j.attempts>=3 then delete from internal_document_jobs where document_id=p_id; end if;
    elsif j.kind='delete' then
        delete from internal_document_units where document_id=p_id;
        update internal_documents set status='deleted',title='Deleted document',warnings='[]',error_code=null,revision=revision+1 where id=p_id;
        delete from internal_document_jobs where document_id=p_id;
    else
        if jsonb_array_length(p_units)=0 then raise exception 'empty_units'; end if;
        delete from internal_document_units where document_id=p_id;
        for u in select value from jsonb_array_elements(p_units) loop
            insert into internal_document_units(document_id,article_key,heading,department,body,start_paragraph,end_paragraph)
            values(p_id,u->>'article_key',u->>'heading',u->>'department',u->>'body',(u->>'start_paragraph')::integer,(u->>'end_paragraph')::integer);
        end loop;
        update internal_documents set status='review',warnings=p_warnings,warnings_acknowledged=false,error_code=null,revision=revision+1 where id=p_id;
        delete from internal_document_jobs where document_id=p_id;
    end if;
    insert into internal_document_events(document_id,action) values(p_id,case when p_error is null then j.kind||'_completed' else 'worker_error' end);
end $$;

revoke all on function public.internal_document_enqueue(uuid,uuid), public.internal_document_action(uuid,uuid,jsonb), public.internal_document_claim(), public.internal_document_finish(uuid,uuid,jsonb,jsonb,text), public.internal_admin_rate_limit(text,integer,integer) from public,anon,authenticated;
grant execute on function public.internal_document_enqueue(uuid,uuid), public.internal_document_action(uuid,uuid,jsonb), public.internal_document_claim(), public.internal_document_finish(uuid,uuid,jsonb,jsonb,text), public.internal_admin_rate_limit(text,integer,integer) to service_role;
commit;
