const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { PGlite } = require(require.resolve('@electric-sql/pglite', { paths: [path.join(__dirname, '../../web')] }))
async function main() {
 const db = new PGlite()
 await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
 create schema storage;
 create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
 create table storage.objects(id integer,bucket_id text);
 alter table storage.objects enable row level security;
 grant usage on schema storage to anon,authenticated,service_role;
 grant all on storage.objects to anon,authenticated,service_role;
 create policy broad_policy on storage.objects for all to anon,authenticated using(true) with check(true);
 insert into storage.objects values(1,'board-attachments'),(2,'other');`)
 await db.exec(fs.readFileSync(path.join(__dirname,'../../db/migrations/202610050001_board.sql'),'utf8'))
 for (const role of ['anon','authenticated']) {
  await db.exec(`set role ${role}`)
  await assert.rejects(db.exec('select * from board_posts'))
  await assert.rejects(db.exec('select * from board_request_limits'))
  await assert.rejects(db.query('select board_rate_limit($1,2,900)',['a'.repeat(64)]))
  assert.deepEqual((await db.exec('select id from storage.objects'))[0].rows,[{id:2}])
  await assert.rejects(db.exec("insert into storage.objects values(3,'board-attachments')"))
  await db.exec('reset role')
 }
 await db.exec('set role service_role')
 const insert = `insert into board_posts(author_name,title,body,category,status,password_hash,published_at)
 values('Author','Title','Body','general','published','fixture',now()) returning id`
 const id = (await db.exec(insert))[0].rows[0].id
 const changed = await db.query('update board_posts set revision=revision+1,title=$1 where id=$2 and revision=0 returning id',['Changed',id])
 assert.equal(changed.rows.length,1)
 assert.equal((await db.query('update board_posts set revision=revision+1 where id=$1 and revision=0 returning id',[id])).rows.length,0)
 await assert.rejects(db.query("update board_posts set status='published',published_at=null where id=$1",[id]))
 await assert.rejects(db.query("update board_posts set attachments='[1,2,3,4]' where id=$1",[id]))
 const key='a'.repeat(64)
 for (const expected of [true,true,false]) assert.equal((await db.query('select board_rate_limit($1,2,900) as permitted',[key])).rows[0].permitted,expected)
 await db.query("update board_request_limits set window_start=now()-interval '16 minutes' where key=$1",[key])
 assert.equal((await db.query('select board_rate_limit($1,2,900) as permitted',[key])).rows[0].permitted,true)
 await db.exec('reset role')
 assert.equal((await db.exec("select public from storage.buckets where id='board-attachments'"))[0].rows[0].public,false)
 await db.close(); console.log('board DB permissions, constraints, concurrency and rate limits passed')
}
main().catch(error => { console.error(error); process.exit(1) })
