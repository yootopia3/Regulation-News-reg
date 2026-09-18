const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { PGlite } = require(require.resolve('@electric-sql/pglite', { paths: [path.join(__dirname, '../../web')] }))
async function main() {
 const db=new PGlite()
 await db.exec(`create role anon; create role authenticated; create role service_role bypassrls;
 create schema storage; create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
 create table storage.objects(id integer,bucket_id text);
 create table articles(id uuid primary key,category text,agency text,link text,published_at timestamptz);
 grant all on articles to service_role;`)
 const migrate=async name=>db.exec(fs.readFileSync(path.join(__dirname,'../../db/migrations',name),'utf8'))
 for(const file of ['202609100001_internal_documents.sql','202609100002_sanction_inspections.sql','202609100003_inspection_publications.sql','202609170001_sanction_automation.sql']) await migrate(file)
 const actor='00000000-0000-4000-8000-000000000001', old='00000000-0000-4000-8000-000000000002', org='00000000-0000-4000-8000-000000000003'
 await db.query("insert into internal_documents(id,title,document_kind,effective_date,sha256,object_key,created_by,status) values($1,'Fixture','allocation','2020-01-01',$2,'old.hwp',$3,'active')",[old,'a'.repeat(64),actor])
 const article=(await db.exec("insert into articles values(gen_random_uuid(),'sanction_notice','FSS_SANCTION','https://www.fss.or.kr/a',now()) returning id"))[0].rows[0].id
 await db.query('select inspection_enqueue($1,$2,gen_random_uuid())',[article,actor])
 let job=(await db.exec('select inspection_claim() as j'))[0].rows[0].j
 await db.query('select inspection_finish($1,$2,$3,null)',[job.id,job.lease_token,{status:'needs_review',document_versions:{[old]:0}}])
 let rev=(await db.query('select review_revision from sanction_inspections where id=$1',[job.id])).rows[0].review_revision
 await db.query('select inspection_auto_publish($1,$2,$3)',[job.id,rev,{items:[{title:'fixture'}]}])
 await migrate('202609180001_organization_basis.sql')
 assert.deepEqual((await db.exec('select inspection_versions() as v'))[0].rows[0].v,{})
 assert.equal((await db.exec('select report from sanction_publications'))[0].rows[0].report,null)
 assert.equal((await db.exec('select status from sanction_inspections'))[0].rows[0].status,'stale')
 await assert.rejects(db.query('select inspection_enqueue($1,$2,gen_random_uuid())',[article,actor]))
 for(const role of ['anon','authenticated']) {
  await db.exec(`set role ${role}`)
  await assert.rejects(db.exec('select organization_names from internal_document_units'))
  await assert.rejects(db.exec('select inspection_versions()'))
  await db.exec('reset role')
 }
 await db.exec('set role service_role')
 await db.query("insert into internal_documents(id,title,document_kind,effective_date,sha256,object_key,created_by) values($1,'Fixture org','organization','2020-01-01',$2,'org.hwp',$3)",[org,'b'.repeat(64),actor])
 await db.query('select internal_document_enqueue($1,$2)',[org,actor])
 job=(await db.exec('select internal_document_claim() as j'))[0].rows[0].j
 await db.query('select internal_document_finish($1,$2,$3,$4,null)',[org,job.lease_token,[{article_key:'6',heading:'조직',body:'조직은 여신심사부 및 인사부로 구성한다.',department:'',start_paragraph:1,end_paragraph:3,organization_names:['여신심사부','인사부']}],[]])
 const row=async()=>(await db.query('select * from internal_documents where id=$1',[org])).rows[0]
 const action=async input=>db.query('select internal_document_action($1,$2,$3)',[org,actor,input])
 const edit=names=>({action:'review',revision:0,units:[{article_key:'6',department:'',reviewed:true,organization_names:names}],warnings_acknowledged:true})
 for(const names of [['가상부서'],['여신심사부','여신심사부'],['\t\t'],['\n\n']]) await assert.rejects(action({...edit(names),revision:(await row()).revision}))
 await assert.rejects(action({...edit(['인사부']),revision:null}))
 await action({...edit([]),revision:(await row()).revision})
 await assert.rejects(action({action:'activate',revision:(await row()).revision}))
 await action({...edit(['여신심사부','인사부']),revision:(await row()).revision})
 await action({action:'activate',revision:(await row()).revision})
 assert.deepEqual((await db.exec('select inspection_versions() as v'))[0].rows[0].v,{[org]:(await row()).revision})
 await db.query('select inspection_enqueue($1,$2,gen_random_uuid())',[article,actor])
 job=(await db.exec('select inspection_claim() as j'))[0].rows[0].j
 assert.deepEqual(job.versions,{[org]:(await row()).revision})
 await action({action:'delete',revision:(await row()).revision})
 assert.equal((await db.exec('select status from sanction_inspections'))[0].rows[0].status,'stale')
 await db.close(); console.log('organization basis DB checks passed')
}
main().catch(error=>{console.error(error);process.exitCode=1})
