-- Private runtime connection settings; no API key plaintext is stored here.
begin;
create table public.sanction_ai_connection (
  id boolean primary key default true check (id),
  base_url text not null check (char_length(base_url) between 8 and 500),
  protocol text not null check (protocol in ('responses', 'chat_completions')),
  model text not null check (char_length(model) between 1 and 200),
  api_key_ciphertext text not null check (api_key_ciphertext like 'v1.%' and char_length(api_key_ciphertext) between 40 and 8000),
  key_last4 text not null check (char_length(key_last4) = 4),
  revision integer not null check (revision > 0),
  updated_by uuid not null,
  updated_at timestamptz not null default now()
);
alter table public.sanction_ai_connection enable row level security;
revoke all on public.sanction_ai_connection from public, anon, authenticated;
grant select, insert, update on public.sanction_ai_connection to service_role;

create function public.sanction_ai_connection_save(
  p_revision integer, p_base_url text, p_protocol text, p_model text,
  p_ciphertext text, p_last4 text, p_actor uuid
) returns integer language plpgsql security invoker set search_path = public, pg_temp as $$
declare current_revision integer;
begin
  perform pg_advisory_xact_lock(hashtext('sanction_ai_connection'));
  select revision into current_revision from sanction_ai_connection where id = true;
  if p_revision is null or p_revision <> coalesce(current_revision, 0) then
    raise exception 'connection_conflict' using errcode = '40001';
  end if;
  insert into sanction_ai_connection(id,base_url,protocol,model,api_key_ciphertext,key_last4,revision,updated_by)
  values(true,p_base_url,p_protocol,p_model,p_ciphertext,p_last4,p_revision+1,p_actor)
  on conflict(id) do update set base_url=excluded.base_url,protocol=excluded.protocol,
    model=excluded.model,api_key_ciphertext=excluded.api_key_ciphertext,key_last4=excluded.key_last4,
    revision=excluded.revision,updated_by=excluded.updated_by,updated_at=now();
  return p_revision+1;
end $$;
revoke all on function public.sanction_ai_connection_save(integer,text,text,text,text,text,uuid) from public, anon, authenticated;
grant execute on function public.sanction_ai_connection_save(integer,text,text,text,text,text,uuid) to service_role;
commit;
