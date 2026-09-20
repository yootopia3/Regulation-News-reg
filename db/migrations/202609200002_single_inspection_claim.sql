-- Manual verification must never claim or expire another article's job.
begin;
create function public.inspection_claim_single(p_id uuid,p_article uuid,p_versions jsonb) returns jsonb
language plpgsql set search_path=public,pg_temp as $$
declare job sanction_inspections;
begin
 perform pg_advisory_xact_lock(20260910);
 select * into job from sanction_inspections where id=p_id for update;
 if not found or job.article_id is distinct from p_article or job.status<>'queued'
    or job.versions is distinct from p_versions or p_versions is distinct from inspection_versions()
 then raise exception 'single_claim_changed'; end if;
 if exists(select 1 from sanction_inspections where id<>p_id and status in ('queued','processing'))
 then raise exception 'single_queue_required'; end if;
 update sanction_inspections set status='processing',lease_token=gen_random_uuid(),
   lease_until=now()+interval '15 minutes',updated_at=now()
 where id=p_id returning * into job;
 return to_jsonb(job);
end $$;
revoke all on function public.inspection_claim_single(uuid,uuid,jsonb) from public,anon,authenticated;
grant execute on function public.inspection_claim_single(uuid,uuid,jsonb) to service_role;
commit;
