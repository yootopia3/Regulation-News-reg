-- Standalone board: ordinary clients must go through the authenticated server API.
begin;
create table public.board_posts (
  id uuid primary key default gen_random_uuid(),
  author_name text not null check (char_length(author_name) between 1 and 40),
  title text not null check (char_length(title) between 1 and 150),
  body text not null check (char_length(body) between 1 and 20000),
  category text not null check (category in ('general','notice','resources')),
  status text not null default 'draft' check (status in ('draft','published')),
  password_hash text not null,
  attachments jsonb not null default '[]' check (jsonb_typeof(attachments) = 'array' and jsonb_array_length(attachments) <= 3),
  is_pinned boolean not null default false,
  revision integer not null default 0 check (revision >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  published_at timestamptz,
  constraint board_published_date check (status <> 'published' or published_at is not null)
);
create index board_posts_list_idx on public.board_posts(status, is_pinned desc, published_at desc, id);
alter table public.board_posts enable row level security;
revoke all on public.board_posts from public, anon, authenticated;
grant select, insert, update, delete on public.board_posts to service_role;

create table public.board_request_limits (
  key text primary key,
  window_start timestamptz not null,
  attempts integer not null
);
alter table public.board_request_limits enable row level security;
revoke all on public.board_request_limits from public, anon, authenticated;
grant select, insert, update, delete on public.board_request_limits to service_role;

create function public.board_rate_limit(p_key text, p_limit integer, p_seconds integer)
returns boolean language plpgsql security definer set search_path = public, pg_temp as $$
declare n integer; t timestamptz := clock_timestamp();
begin
  if p_limit < 1 or p_seconds < 1 or p_seconds > 86400 or char_length(p_key) <> 64 then
    raise exception 'invalid rate limit';
  end if;
  delete from board_request_limits where window_start < t - interval '1 day';
  insert into board_request_limits(key, window_start, attempts) values(p_key,t,1)
  on conflict(key) do update set
    attempts = case when board_request_limits.window_start <= t - make_interval(secs => p_seconds) then 1 else board_request_limits.attempts + 1 end,
    window_start = case when board_request_limits.window_start <= t - make_interval(secs => p_seconds) then t else board_request_limits.window_start end
  returning attempts into n;
  return n <= p_limit;
end $$;
revoke all on function public.board_rate_limit(text,integer,integer) from public, anon, authenticated;
grant execute on function public.board_rate_limit(text,integer,integer) to service_role;

insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('board-attachments','board-attachments',false,3145728,
  array['application/pdf','application/octet-stream','application/msword','application/vnd.ms-excel',
    'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'])
on conflict(id) do update set public=false, file_size_limit=excluded.file_size_limit, allowed_mime_types=excluded.allowed_mime_types;
-- Restrictive policies also defeat unrelated broad allow policies for this bucket.
create policy board_objects_private on storage.objects as restrictive for all to anon, authenticated
using(bucket_id <> 'board-attachments') with check(bucket_id <> 'board-attachments');
commit;
