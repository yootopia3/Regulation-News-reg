begin;
create table public.sanction_inspections (
 id uuid primary key default gen_random_uuid(),
 article_id uuid not null unique references public.articles(id) on delete cascade,
 status text not null check(status in ('queued','processing','needs_review','failed','stale')),
 versions jsonb not null,
 result jsonb,
 error_code text,
 lease_token uuid,
 lease_until timestamptz,
 created_by uuid not null,
 request_id uuid not null,
 updated_at timestamptz not null default now()
);
alter table public.sanction_inspections enable row level security;
revoke all on public.sanction_inspections from public,anon,authenticated;
grant all on public.sanction_inspections to service_role;

create function public.inspection_versions() returns jsonb language sql stable
set search_path=public,pg_temp as $$
 select coalesce(jsonb_object_agg(id::text,revision),'{}'::jsonb)
 from internal_documents where status='active';
$$;

create function public.inspection_enqueue(p_article uuid,p_actor uuid,p_request uuid) returns uuid
language plpgsql set search_path=public,pg_temp as $$
declare v jsonb; job sanction_inspections; result_id uuid;
begin
 perform pg_advisory_xact_lock(20260910);
 if not exists(select 1 from articles where id=p_article and category='sanction_notice'
   and agency in ('FSS_SANCTION','FSS_MGMT_NOTICE')) then raise exception 'invalid_article'; end if;
 v := inspection_versions();
 if v='{}'::jsonb then raise exception 'no_active_documents'; end if;
 select * into job from sanction_inspections where article_id=p_article for update;
 if found and job.request_id=p_request then return job.id; end if;
 if found and job.versions=v and (job.status='queued' or
    (job.status='processing' and job.lease_until>now())) then return job.id; end if;
 insert into sanction_inspections(article_id,status,versions,created_by,request_id)
 values(p_article,'queued',v,p_actor,p_request) on conflict(article_id) do update
 set status='queued',versions=v,result=null,error_code=null,lease_token=null,lease_until=null,
 created_by=p_actor,request_id=p_request,updated_at=now() returning id into result_id;
 return result_id;
end $$;

create function public.inspection_claim() returns jsonb
language plpgsql set search_path=public,pg_temp as $$
declare job sanction_inspections;
begin
 perform pg_advisory_xact_lock(20260910);
 update sanction_inspections set status='failed',error_code='lease_expired',lease_token=null,lease_until=null
 where status='processing' and lease_until<=now();
 select * into job from sanction_inspections where status='queued' order by updated_at,id limit 1 for update;
 if not found then return null; end if;
 update sanction_inspections set status='processing',lease_token=gen_random_uuid(),lease_until=now()+interval '15 minutes',updated_at=now()
 where id=job.id returning * into job;
 return to_jsonb(job);
end $$;

create function public.inspection_finish(p_id uuid,p_token uuid,p_result jsonb,p_error text) returns void
language plpgsql set search_path=public,pg_temp as $$
declare job sanction_inspections;
begin
 perform pg_advisory_xact_lock(20260910);
 select * into job from sanction_inspections where id=p_id for update;
 if not found or job.status<>'processing' or job.lease_token is distinct from p_token or job.lease_until<=now()
 then raise exception 'lease_conflict'; end if;
 if job.versions is distinct from inspection_versions() then
   update sanction_inspections set status='stale',result=null,error_code='documents_changed',lease_token=null,lease_until=null where id=p_id;
   return;
 end if;
 if p_error is null and (p_result is null or p_result->>'status' is distinct from 'needs_review'
    or p_result->'document_versions' is distinct from job.versions) then raise exception 'invalid_result'; end if;
 update sanction_inspections set status=case when p_error is null then 'needs_review' else 'failed' end,
 result=case when p_error is null then p_result else null end,error_code=p_error,lease_token=null,lease_until=null,updated_at=now() where id=p_id;
end $$;

-- Clearing drafts on document changes also clears retained private evidence on deletion.
create function public.inspection_invalidate() returns trigger language plpgsql
set search_path=public,pg_temp as $$
begin
 perform pg_advisory_xact_lock(20260910);
 update sanction_inspections set status='stale',result=null,error_code='documents_changed',lease_token=null,lease_until=null,updated_at=now()
 where status<>'stale' and versions is distinct from inspection_versions();
 return null;
end $$;
create trigger inspection_documents_changed after insert or update or delete on public.internal_documents
for each statement execute function public.inspection_invalidate();

revoke all on function public.inspection_versions(),public.inspection_enqueue(uuid,uuid,uuid),public.inspection_claim(),public.inspection_finish(uuid,uuid,jsonb,text),public.inspection_invalidate() from public,anon,authenticated;
grant execute on function public.inspection_versions(),public.inspection_enqueue(uuid,uuid,uuid),public.inspection_claim(),public.inspection_finish(uuid,uuid,jsonb,text),public.inspection_invalidate() to service_role;
commit;
