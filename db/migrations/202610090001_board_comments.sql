-- Board comments: authenticated server access only. Requires 202610050001_board.sql.
begin;
create table public.board_comments (
  id uuid primary key default gen_random_uuid(),
  post_id uuid not null references public.board_posts(id) on delete cascade,
  author_name text not null check (char_length(author_name) between 1 and 40 and char_length(btrim(author_name)) > 0),
  body text not null check (char_length(body) between 1 and 2000 and char_length(btrim(body)) > 0),
  password_hash text not null,
  revision integer not null default 0 check (revision >= 0),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index board_comments_post_created_idx on public.board_comments(post_id, created_at desc, id desc);
alter table public.board_comments enable row level security;
revoke all on public.board_comments from public, anon, authenticated;
grant select, insert, update, delete on public.board_comments to service_role;

-- Serialize comment writes with a concurrent unpublish/delete of the parent.
create function public.board_comment_published_post() returns trigger
language plpgsql security invoker set search_path = public, pg_temp as $$
declare parent_status text; parent_id uuid;
begin
  if tg_op = 'DELETE' then parent_id := old.post_id; else parent_id := new.post_id; end if;
  select status into parent_status from board_posts where id = parent_id for share;
  -- The parent is already absent during its ON DELETE CASCADE.
  if tg_op = 'DELETE' and not found then return old; end if;
  if parent_status is distinct from 'published' then
    raise exception 'comment_post_not_published' using errcode = '23514';
  end if;
  if tg_op = 'DELETE' then return old; end if;
  return new;
end $$;
revoke all on function public.board_comment_published_post() from public, anon, authenticated;
grant execute on function public.board_comment_published_post() to service_role;
create trigger board_comments_published_parent before insert or update or delete on public.board_comments
for each row execute function public.board_comment_published_post();
commit;
