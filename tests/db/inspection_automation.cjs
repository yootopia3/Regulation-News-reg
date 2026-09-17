const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { PGlite } = require(require.resolve('@electric-sql/pglite', { paths: [path.join(__dirname, '../../web')] }))
async function main() {
 const db = new PGlite()
 await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
 create table articles(id uuid primary key, category text, agency text, link text, published_at timestamptz);
 create table internal_documents(id uuid primary key,revision integer,status text);
 grant all on articles,internal_documents to service_role;`)
 for (const file of ['202609100002_sanction_inspections.sql','202609100003_inspection_publications.sql','202609170001_sanction_automation.sql'])
  await db.exec(fs.readFileSync(path.join(__dirname,'../../db/migrations',file),'utf8'))
 const doc='00000000-0000-4000-8000-000000000001'
 for (const role of ['anon','authenticated']) {
  await db.exec(`set role ${role}`)
  await assert.rejects(db.exec("select inspection_auto_enqueue(now()-interval '1 day',3)"))
  await assert.rejects(db.query('select inspection_auto_publish($1,0,$2)',[doc,{items:[]}]))
  await assert.rejects(db.query('select inspection_auto_attention($1,0)',[doc]))
  await db.exec('reset role')
 }
 await db.exec('set role service_role')
 await db.query("insert into internal_documents values($1,1,'active')",[doc])
 await db.exec(`insert into articles select gen_random_uuid(),'sanction_notice','FSS_SANCTION',
 'https://www.fss.or.kr/view?examMgmtNo=123&emOpenSeq=1&pageIndex='||n,now()-n*interval '1 minute' from generate_series(1,2) n`)
 const enqueue=async()=> (await db.exec("select inspection_auto_enqueue(now()-interval '1 day',3) as n"))[0].rows[0].n
 assert.equal(await enqueue(),1) // Alias URLs do not create duplicate paid jobs.
 assert.equal(await enqueue(),0)
 let job=(await db.exec('select inspection_claim() as j'))[0].rows[0].j
 const finish=async(j)=>db.query('select inspection_finish($1,$2,$3,null)',[j.id,j.lease_token,{status:'needs_review',document_versions:{[doc]:1}}])
 await finish(job)
 const row=async()=> (await db.query('select * from sanction_inspections where id=$1',[job.id])).rows[0]
 const report={items:[{title:'Public fixture'}]}
 let revision=(await row()).review_revision
 await assert.rejects(db.query('select inspection_auto_publish($1,null,$2)',[job.id,report]))
 await assert.rejects(db.query('select inspection_auto_publish($1,$2,$3)',[job.id,revision-1,report]))
 await db.query('select inspection_auto_publish($1,$2,$3)',[job.id,revision,report])
 assert.equal((await row()).automation_status,'published')
 const alias=(await db.query('select id from articles where id<>$1',[job.article_id])).rows[0].id
 assert.equal((await db.query('select inspection_publication_alias($1) as id',[alias])).rows[0].id,job.id)
 assert.equal((await db.exec('select publication_source from sanction_publications'))[0].rows[0].publication_source,'automatic')
 await assert.rejects(db.query('select inspection_auto_publish($1,$2,$3)',[job.id,revision,report]))
 revision=(await row()).review_revision
 await db.query("select inspection_review_action($1,$2,$3,'withdraw')",[job.id,doc,revision])
 assert.equal((await row()).automation_status,'manual')
 assert.equal((await db.exec('select report from sanction_publications'))[0].rows[0].report,null)
 assert.equal((await db.query('select inspection_publication_alias($1) as id',[alias])).rows[0].id,null)
 await assert.rejects(db.query('select inspection_auto_publish($1,$2,$3)',[job.id,(await row()).review_revision,report]))
 assert.equal(await enqueue(),0) // Manual withdrawal is not silently undone.
 // Explicit reanalysis can opt back into automation, but saving by a person wins.
 await db.query('select inspection_enqueue($1,$2,gen_random_uuid())',[job.article_id,doc])
 job=(await db.exec('select inspection_claim() as j'))[0].rows[0].j
 await finish(job)
 revision=(await row()).review_revision
 await db.query("select inspection_review_action($1,$2,$3,'save',$4)",[job.id,doc,revision,report])
 await assert.rejects(db.query('select inspection_auto_publish($1,$2,$3)',[job.id,revision,report]))
 await assert.rejects(db.query('select inspection_auto_publish($1,$2,$3)',[job.id,(await row()).review_revision,report]))
 // A rule change invalidates results; batches do not repeatedly re-charge failed/stale jobs.
 await db.query('update internal_documents set revision=2 where id=$1',[doc])
 assert.equal((await row()).status,'stale')
 assert.equal(await enqueue(),0)
 assert.equal((await db.exec('select report from sanction_publications'))[0].rows[0].report,null)
 await db.close()
 console.log('inspection automation DB checks passed')
}
main().catch(()=>{console.error('inspection automation DB checks failed');process.exitCode=1})
