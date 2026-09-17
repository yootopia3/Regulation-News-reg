begin;
alter table public.sanction_inspections add column automation_status text not null default 'none'
 check(automation_status in ('none','pending','published','needs_attention','manual'));
alter table public.sanction_publications add column publication_source text not null default 'manual'
 check(publication_source in ('manual','automatic'));
alter table public.sanction_inspections alter column created_by drop not null;

create function public.inspection_automation_reset() returns trigger language plpgsql set search_path=public,pg_temp as $$
begin
 if tg_op='INSERT' then
  if new.status='queued' then new.automation_status:='pending'; end if;
 elsif new.request_id is distinct from old.request_id then new.automation_status:='pending';
 elsif new.status in ('failed','stale') then new.automation_status:='needs_attention';
 end if;
 return new;
end $$;
create trigger inspection_automation_reset before insert or update on public.sanction_inspections
 for each row execute function public.inspection_automation_reset();

create function public.inspection_source_key(p_agency text,p_link text) returns text
language sql immutable set search_path=public,pg_temp as $$
 select p_agency||':'||case
 when p_link ~ '[?&]examMgmtNo=[^&]+' and p_link ~ '[?&]emOpenSeq=[^&]+'
 then substring(p_link from '[?&]examMgmtNo=([^&]+)')||':'||substring(p_link from '[?&]emOpenSeq=([^&]+)')
 else p_link end;
$$;

create function public.inspection_publication_alias(p_article uuid) returns uuid
language sql stable set search_path=public,pg_temp as $$
 select p.inspection_id from articles requested
 join articles source on inspection_source_key(source.agency,source.link)=inspection_source_key(requested.agency,requested.link)
 join sanction_publications p on p.article_id=source.id and p.status='published'
 where requested.id=p_article order by p.published_at desc limit 1;
$$;

create function public.inspection_auto_enqueue(p_since timestamptz,p_limit integer default 3) returns integer
language plpgsql set search_path=public,pg_temp as $$
declare a record; n integer:=0; slots integer;
begin
 perform pg_advisory_xact_lock(20260910);
 if p_limit is null or p_limit<1 or p_limit>10 or p_since is null or p_since>now() then raise exception 'invalid_batch'; end if;
 if inspection_versions()='{}'::jsonb then return 0; end if;
 select greatest(0,p_limit-count(*)::integer) into slots from sanction_inspections where status in ('queued','processing');
 for a in select * from articles where category='sanction_notice' and agency in ('FSS_SANCTION','FSS_MGMT_NOTICE')
   and published_at>=greatest(p_since,now()-interval '90 days')
   order by published_at desc,id
 loop
  exit when n>=slots;
  if not exists(select 1 from sanction_inspections j join articles prior on prior.id=j.article_id
    where inspection_source_key(prior.agency,prior.link)=inspection_source_key(a.agency,a.link)) then
   perform inspection_enqueue(a.id,null,gen_random_uuid()); n:=n+1;
  end if;
 end loop;
 return n;
end $$;

create function public.inspection_auto_publish(p_id uuid,p_revision integer,p_report jsonb) returns void
language plpgsql set search_path=public,pg_temp as $$
declare job sanction_inspections; rev integer;
begin
 perform pg_advisory_xact_lock(20260910);
 select * into job from sanction_inspections where id=p_id for update;
 if not found or job.review_revision is distinct from p_revision or job.status<>'needs_review'
  or job.automation_status<>'pending' or job.review_draft is not null
  or job.versions is distinct from inspection_versions() then raise exception 'review_conflict'; end if;
 if p_report is null or jsonb_typeof(p_report->'items') is distinct from 'array' then raise exception 'invalid_report'; end if;
 update sanction_inspections set review_revision=review_revision+1,review_draft=p_report,automation_status='published'
 where id=p_id returning review_revision into rev;
 insert into sanction_publications(inspection_id,article_id,revision,status,report,published_at,publication_source)
 values(p_id,job.article_id,rev,'published',p_report,now(),'automatic') on conflict(inspection_id) do update
 set revision=rev,status='published',report=p_report,published_at=now(),publication_source='automatic';
 insert into inspection_review_events(inspection_id,action,revision) values(p_id,'automatic_publish',rev);
end $$;

create function public.inspection_auto_attention(p_id uuid,p_revision integer) returns void
language sql set search_path=public,pg_temp as $$
 update sanction_inspections set automation_status='needs_attention' where id=p_id
 and review_revision=p_revision and automation_status='pending' and status='needs_review';
$$;

-- Preserve the existing manual approval route, explicitly marking its provenance.
create or replace function public.inspection_review_action(p_id uuid,p_actor uuid,p_revision integer,p_action text,p_report jsonb default null)
returns integer language plpgsql set search_path=public,pg_temp as $$
declare job sanction_inspections; rev integer;
begin
 perform pg_advisory_xact_lock(20260910);
 select * into job from sanction_inspections where id=p_id for update;
 if not found or job.review_revision is distinct from p_revision then raise exception 'review_conflict'; end if;
 if p_action not in ('save','publish','withdraw') then raise exception 'invalid_action'; end if;
 if p_action<>'withdraw' and (job.status<>'needs_review' or job.versions is distinct from inspection_versions()) then raise exception 'review_conflict'; end if;
 if p_action='save' and (p_report is null or jsonb_typeof(p_report)<>'object') then raise exception 'invalid_report'; end if;
 if p_action='publish' and job.review_draft is null then raise exception 'review_required'; end if;
 update sanction_inspections set review_revision=review_revision+1,automation_status='manual',
 review_draft=case when p_action='save' then p_report else review_draft end where id=p_id returning review_revision into rev;
 if p_action='publish' then
  insert into sanction_publications(inspection_id,article_id,revision,status,report,published_at,publication_source)
  values(p_id,job.article_id,rev,'published',job.review_draft,now(),'manual') on conflict(inspection_id) do update
  set revision=rev,status='published',report=job.review_draft,published_at=now(),publication_source='manual';
 end if;
 insert into inspection_review_events(inspection_id,actor,action,revision) values(p_id,p_actor,p_action,rev);
 return rev;
end $$;
revoke all on function public.inspection_automation_reset(),public.inspection_source_key(text,text),public.inspection_auto_enqueue(timestamptz,integer),public.inspection_auto_publish(uuid,integer,jsonb),public.inspection_auto_attention(uuid,integer) from public,anon,authenticated;
revoke all on function public.inspection_publication_alias(uuid) from public,anon,authenticated;
grant execute on function public.inspection_publication_alias(uuid) to service_role;
grant execute on function public.inspection_automation_reset(),public.inspection_source_key(text,text),public.inspection_auto_enqueue(timestamptz,integer),public.inspection_auto_publish(uuid,integer,jsonb),public.inspection_auto_attention(uuid,integer) to service_role;
commit;
