const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { PGlite } = require(require.resolve('@electric-sql/pglite', { paths: [path.join(__dirname, '../../web')] }))
async function main() {
 const db = new PGlite()
 await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
 create table articles(id uuid primary key,category text,agency text);
 create table internal_documents(id uuid primary key,revision integer,status text);
 grant all on articles,internal_documents to service_role;`)
 await db.exec(fs.readFileSync(path.join(__dirname, '../../db/migrations/202609100002_sanction_inspections.sql'), 'utf8'))
 await db.exec(fs.readFileSync(path.join(__dirname, '../../db/migrations/202609100003_inspection_publications.sql'), 'utf8'))
 const doc='00000000-0000-4000-8000-000000000001', article='00000000-0000-4000-8000-000000000002'
 await db.query("insert into articles values($1,'sanction_notice','FSS_SANCTION')",[article])
 for (const role of ['anon','authenticated']) {
  await db.exec(`set role ${role}`)
  await assert.rejects(db.exec('select * from sanction_inspections'))
  await assert.rejects(db.exec('select * from sanction_publications'))
  await assert.rejects(db.query("select inspection_review_action($1,$1,0,'publish')",[article]))
  await assert.rejects(db.exec('select inspection_claim()'))
  await assert.rejects(db.query('select inspection_enqueue($1,$1,$1)',[article]))
  await db.exec('reset role')
 }
 await db.exec('set role service_role')
 let request = article
 const enqueue = async () => (await db.query('select inspection_enqueue($1,$1,$2) as id',[article,request])).rows[0].id
 const claim = async () => (await db.query('select inspection_claim() as job')).rows[0].job
 const row = async () => (await db.query('select * from sanction_inspections')).rows[0]
 await assert.rejects(enqueue())
 await db.query("insert into internal_documents values($1,1,'active')",[doc])
 const id = await enqueue(); assert.equal(await enqueue(), id)
 let job = await claim(); assert.equal(await claim(), null)
 assert.equal(await enqueue(), id)
 const result = {status:'needs_review',document_versions:{[doc]:1},matches:['PRIVATE_CANARY']}
 await assert.rejects(db.query('select inspection_finish($1,$2,$3,null)',[id,article,result]))
 await db.query('select inspection_finish($1,$2,$3,null)',[id,job.lease_token,result])
 assert.equal((await row()).status,'needs_review')
 const review = async (action, revision, report = null) => (await db.query('select inspection_review_action($1,$2,$3,$4,$5) as rev',[id,doc,revision,action,report])).rows[0].rev
 let revision = (await row()).review_revision
 await assert.rejects(review('publish', revision)) // saved review is mandatory
 revision = await review('save', revision, {items:[{title:'Public-only fixture'}]})
 await assert.rejects(review('publish', revision-1)) // stale editor cannot publish
 revision = await review('publish', revision)
 assert.equal((await db.query('select status from sanction_publications')).rows[0].status,'published')
 assert.equal(JSON.stringify((await db.query('select report from sanction_publications')).rows).includes('PRIVATE_CANARY'),false)
 revision = await review('withdraw', revision)
 assert.equal((await db.query('select report from sanction_publications')).rows[0].report,null)
 revision = await review('publish', revision)
 revision = await review('save', revision, {items:[{title:'Edited snapshot'}]})
 assert.equal((await db.query('select report from sanction_publications')).rows[0].report,null)
 await review('publish', revision)
 assert.equal(await enqueue(),id)
 assert.equal((await row()).status,'needs_review') // repeated delivery is idempotent
 request = '00000000-0000-4000-8000-000000000003'
 await enqueue(); assert.equal((await row()).status,'queued') // deliberate completed rerun
 assert.equal((await db.query('select report from sanction_publications')).rows[0].report,null)
 assert.equal((await row()).review_draft,null)
 job = await claim()
 await db.query('select inspection_finish($1,$2,$3,null)',[id,job.lease_token,result])
 revision = await review('save', (await row()).review_revision, {items:[{title:'Current public snapshot'}]})
 await review('publish', revision)
 await db.query('update internal_documents set revision=2 where id=$1',[doc])
 assert.equal((await row()).status,'stale'); assert.equal((await row()).result,null)
 assert.equal((await row()).review_draft,null)
 assert.equal((await db.query('select report from sanction_publications')).rows[0].report,null)
 request = '00000000-0000-4000-8000-000000000004'
 await enqueue(); job=await claim()
 await db.query('delete from internal_documents where id=$1',[doc])
 await assert.rejects(db.query('select inspection_finish($1,$2,$3,null)',[id,job.lease_token,result]))
 assert.equal((await row()).result,null)
 await db.query("insert into internal_documents values($1,3,'active')",[doc])
 request = '00000000-0000-4000-8000-000000000005'
 await enqueue(); job=await claim()
 await db.exec("update sanction_inspections set lease_until=now()-interval '1 second'")
 assert.equal(await claim(),null); assert.equal((await row()).status,'failed')
 request = '00000000-0000-4000-8000-000000000006'
 await enqueue(); assert.ok(await claim())
 await db.close(); console.log('PASS: inspection privileges, idempotency, leases, document invalidation and recovery')
}
main().catch(e=>{console.error(e);process.exitCode=1})
