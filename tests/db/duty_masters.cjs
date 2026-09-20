const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { PGlite } = require(require.resolve('@electric-sql/pglite', { paths: [path.join(__dirname, '../../web')] }))
async function main() {
 const db = new PGlite()
 await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
 create schema storage; create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
 create table storage.objects(id integer,bucket_id text);
 create table articles(id uuid primary key,category text,agency text,link text,published_at timestamptz);
 grant all on articles to service_role;`)
 const migrate = name => db.exec(fs.readFileSync(path.join(__dirname, '../../db/migrations', name), 'utf8'))
 for (const name of ['202609100001_internal_documents.sql','202609100002_sanction_inspections.sql','202609100003_inspection_publications.sql','202609170001_sanction_automation.sql','202609180001_organization_basis.sql']) await migrate(name)
 const actor = '00000000-0000-4000-8000-000000000001'
 const org = (await db.query("insert into internal_documents(id,title,document_kind,effective_date,sha256,object_key,created_by,status) values(gen_random_uuid(),'Fixture','organization','2020-01-01',$1,'fixture.hwp',$2,'active') returning id", ['a'.repeat(64),actor])).rows[0].id
 const article = (await db.exec("insert into articles values(gen_random_uuid(),'sanction_notice','FSS_SANCTION','https://www.fss.or.kr/fixture',now()) returning id"))[0].rows[0].id
 await db.query('select inspection_enqueue($1,$2,gen_random_uuid())', [article,actor])
 let job = (await db.exec('select inspection_claim() as j'))[0].rows[0].j
 await db.query('select inspection_finish($1,$2,$3,null)', [job.id,job.lease_token,{status:'needs_review',document_versions:{[org]:0}}])
 let revision = (await db.exec('select review_revision from sanction_inspections'))[0].rows[0].review_revision
 await db.query('select inspection_auto_publish($1,$2,$3)', [job.id,revision,{items:[{title:'fixture'}]}])
 await migrate('202609200001_duty_masters.sql')
 assert.deepEqual((await db.exec('select inspection_versions() as v'))[0].rows[0].v,{[org]:0})
 assert.equal((await db.exec('select status from sanction_publications'))[0].rows[0].status,'published')
 for (const role of ['anon','authenticated']) {
  await db.exec(`set role ${role}`)
  await assert.rejects(db.exec('select * from inspection_duty_masters'))
  await assert.rejects(db.query('select inspection_master_activate($1)',[org]))
  await db.exec('reset role')
 }
 await db.exec('set role service_role')
 const payload = {version:'fixture-v1',scope:'headquarters_only',duties:[{id:'HQ-001'}]}
 const master = (await db.query('insert into inspection_duty_masters(version,fingerprint,payload) values($1,$2,$3) returning id',['fixture-v1','b'.repeat(64),payload])).rows[0].id
 assert.equal((await db.exec('select status from sanction_publications'))[0].rows[0].status,'published')
 await db.query('select inspection_master_activate($1)',[master])
 assert.deepEqual((await db.exec('select inspection_versions() as v'))[0].rows[0].v,{[master]:1})
 assert.equal((await db.exec('select status from sanction_inspections'))[0].rows[0].status,'stale')
 assert.equal((await db.exec('select report from sanction_publications'))[0].rows[0].report,null)
 await assert.rejects(db.query("update inspection_duty_masters set version='changed' where id=$1",[master]))
 await assert.rejects(db.query('update inspection_duty_masters set payload=$1 where id=$2',[{...payload,duties:[]},master]))
 await db.query('select inspection_enqueue($1,$2,gen_random_uuid())',[article,actor])
 job = (await db.exec('select inspection_claim() as j'))[0].rows[0].j
 assert.deepEqual(job.versions,{[master]:1})
 const second = (await db.query('insert into inspection_duty_masters(version,fingerprint,payload) values($1,$2,$3) returning id',['fixture-v2','c'.repeat(64),{...payload,version:'fixture-v2'}])).rows[0].id
 await db.query('select inspection_master_activate($1)',[second])
 await assert.rejects(db.query('select inspection_finish($1,$2,$3,null)',[job.id,job.lease_token,{status:'needs_review',document_versions:job.versions}]))
 assert.deepEqual((await db.exec('select inspection_versions() as v'))[0].rows[0].v,{[second]:1})
 await db.exec('reset role')
 await migrate('202609200002_single_inspection_claim.sql')
 const otherArticle = (await db.exec("insert into articles values(gen_random_uuid(),'sanction_notice','FSS_SANCTION','https://www.fss.or.kr/other-fixture',now()) returning id"))[0].rows[0].id
 await db.query('select inspection_enqueue($1,$2,gen_random_uuid())',[article,actor])
 const target = (await db.query('select id from sanction_inspections where article_id=$1',[article])).rows[0].id
 for (const role of ['anon','authenticated']) {
  await db.exec(`reset role; set role ${role}`)
  await assert.rejects(db.query('select inspection_claim_single($1,$2,$3)',[target,article,{[second]:1}]))
 }
 await db.exec('reset role; set role service_role')
 await assert.rejects(db.query('select inspection_claim_single($1,$2,$3)',[target,otherArticle,{[second]:1}]))
 await assert.rejects(db.query('select inspection_claim_single($1,$2,$3)',[target,article,{[master]:1}]))
 await db.query('select inspection_enqueue($1,$2,gen_random_uuid())',[otherArticle,actor])
 const snapshot = async () => (await db.exec('select * from sanction_inspections order by id'))[0].rows
 const before = await snapshot()
 await assert.rejects(db.query('select inspection_claim_single($1,$2,$3)',[target,article,{[second]:1}]))
 assert.deepEqual(await snapshot(),before)
 await db.query("update sanction_inspections set status='stale' where article_id=$1",[otherArticle])
 const claimed = (await db.query('select inspection_claim_single($1,$2,$3) as j',[target,article,{[second]:1}])).rows[0].j
 assert.equal(claimed.id,target)
 assert.equal(claimed.article_id,article)
 assert.equal(claimed.status,'processing')
 await db.query('select inspection_enqueue($1,$2,gen_random_uuid())',[otherArticle,actor])
 const raced = await snapshot()
 await assert.rejects(db.query('select inspection_claim_single($1,$2,$3)',[target,article,{[second]:1}]))
 assert.deepEqual(await snapshot(),raced)
 await db.close(); console.log('duty master DB checks passed')
}
main().catch(error=>{ console.error(error);process.exit(1) })
