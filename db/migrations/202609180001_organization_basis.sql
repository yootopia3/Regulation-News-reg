-- Apply before deploying organization support. Pauses legacy-basis analysis and withdraws old snapshots.
begin;
select pg_advisory_xact_lock(20260910);
alter table public.internal_documents drop constraint internal_documents_document_kind_check;
alter table public.internal_documents add constraint internal_documents_document_kind_check check(document_kind in ('allocation','analysis','organization'));
alter table public.internal_document_units add column organization_names jsonb not null default '[]';
create function public.internal_organization_names_valid(p_names jsonb,p_body text) returns boolean
language plpgsql immutable set search_path=public,pg_temp as $$
declare n jsonb;
begin
 if p_names is null or p_body is null or jsonb_typeof(p_names)<>'array' then return false; end if;
 if jsonb_array_length(p_names)>200 then return false; end if;
 if (select count(*)<>count(distinct value) from jsonb_array_elements(p_names)) then return false; end if;
 for n in select value from jsonb_array_elements(p_names) loop
  if jsonb_typeof(n)<>'string' or length(regexp_replace(n#>>'{}','[[:space:]]','','g')) not between 2 and 120
   or position(regexp_replace(n#>>'{}','[[:space:]]','','g') in regexp_replace(p_body,'[[:space:]]','','g'))=0 then return false; end if;
 end loop;
 return true;
end $$;
alter table public.internal_document_units add constraint internal_organization_names_check check(public.internal_organization_names_valid(organization_names,body));
revoke all on function public.internal_organization_names_valid(jsonb,text) from public,anon,authenticated;
grant execute on function public.internal_organization_names_valid(jsonb,text) to service_role;
create or replace function public.inspection_versions() returns jsonb language sql stable
set search_path=public,pg_temp as $$
 select coalesce(jsonb_object_agg(id::text,revision),'{}'::jsonb)
 from internal_documents where status='active' and document_kind='organization';
$$;

create or replace function public.internal_document_action(p_id uuid,p_actor uuid,p_input jsonb) returns integer
language plpgsql security invoker set search_path=public,pg_temp as $$
declare d internal_documents; u jsonb; requested text := p_input->>'action'; result integer;
begin
    -- Serializes activations across documents as well as competing edits.
    perform pg_advisory_xact_lock(20260910);
    select * into d from internal_documents where id=p_id for update;
    if not found or d.revision is distinct from (p_input->>'revision')::integer then raise exception 'state_conflict'; end if;
    if requested='review' then
        if d.status <> 'review' then raise exception 'state_conflict'; end if;
        for u in select value from jsonb_array_elements(p_input->'units') loop
            if d.document_kind='organization' and (not (u ? 'organization_names') or not internal_organization_names_valid(u->'organization_names',
              (select body from internal_document_units where document_id=p_id and article_key=u->>'article_key'))) then
              raise exception 'invalid_organization_names';
            end if;
            update internal_document_units set department=u->>'department',reviewed=(u->>'reviewed')::boolean,
              organization_names=case when d.document_kind='organization' then u->'organization_names' else organization_names end
              where document_id=p_id and article_key=u->>'article_key';
            if not found then raise exception 'state_conflict'; end if;
        end loop;
        update internal_documents set warnings_acknowledged=(p_input->>'warnings_acknowledged')::boolean where id=p_id;
    elsif requested='activate' then
        if d.status <> 'review' or not d.warnings_acknowledged or d.effective_date > (now() at time zone 'Asia/Seoul')::date
          or not exists(select 1 from internal_document_units where document_id=p_id)
          or exists(select 1 from internal_document_units where document_id=p_id and not reviewed)
          then raise exception 'state_conflict'; end if;
        if d.document_kind='organization' and not exists(select 1 from internal_document_units where document_id=p_id and jsonb_array_length(organization_names)>0) then
          raise exception 'organization_roster_required'; end if;
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

create or replace function public.internal_document_finish(p_id uuid,p_token uuid,p_units jsonb,p_warnings jsonb,p_error text) returns void
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
            insert into internal_document_units(document_id,article_key,heading,department,body,start_paragraph,end_paragraph,organization_names)
            values(p_id,u->>'article_key',u->>'heading',u->>'department',u->>'body',(u->>'start_paragraph')::integer,(u->>'end_paragraph')::integer,coalesce(u->'organization_names','[]'::jsonb));
        end loop;
        update internal_documents set status='review',warnings=p_warnings,warnings_acknowledged=false,error_code=null,revision=revision+1 where id=p_id;
        delete from internal_document_jobs where document_id=p_id;
    end if;
    insert into internal_document_events(document_id,action) values(p_id,case when p_error is null then j.kind||'_completed' else 'worker_error' end);
end $$;

-- Changing the version selector does not itself fire the document trigger.
update public.sanction_inspections set status='stale',result=null,error_code='documents_changed',lease_token=null,lease_until=null,updated_at=now()
where versions is distinct from public.inspection_versions();
commit;
