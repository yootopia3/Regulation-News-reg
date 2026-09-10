// Run with PGLITE_MODULE pointing to an installed @electric-sql/pglite package.
// Uses an in-memory database and synthetic content only; no environment DB URLs.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { PGlite } = require(process.env.PGLITE_MODULE || require.resolve('@electric-sql/pglite', { paths: [path.join(__dirname, '../../web')] }))

async function main() {
    const db = new PGlite()
    await db.exec(`
        create role anon; create role authenticated; create role service_role bypassrls;
        create schema storage;
        create table storage.buckets(id text primary key,name text,public boolean,file_size_limit bigint,allowed_mime_types text[]);
        create table storage.objects(id integer,bucket_id text);
        alter table storage.objects enable row level security;
        grant usage on schema storage,public to anon,authenticated,service_role;
        grant all on storage.objects to anon,authenticated,service_role;
        create policy broad_existing_policy on storage.objects for all to anon,authenticated using(true) with check(true);
    `)
    await db.exec(fs.readFileSync(path.join(__dirname, '../../db/migrations/202609100001_internal_documents.sql'), 'utf8'))
    await db.exec('create table articles(id uuid primary key,category text,agency text); grant all on articles to service_role;')
    await db.exec(fs.readFileSync(path.join(__dirname, '../../db/migrations/202609100002_sanction_inspections.sql'), 'utf8'))
    await db.exec(fs.readFileSync(path.join(__dirname, '../../db/migrations/202609100003_inspection_publications.sql'), 'utf8'))
    await db.exec("insert into storage.objects values(1,'internal-documents'),(2,'public-fixtures')")
    for (const role of ['anon', 'authenticated']) {
        await db.exec(`set role ${role}`)
        assert.deepEqual((await db.query('select id from storage.objects')).rows, [{ id: 2 }])
        await assert.rejects(db.exec("insert into storage.objects values(3,'internal-documents')"))
        for (const table of ['internal_documents','internal_document_units','internal_document_jobs','internal_document_events','internal_admin_limits']) {
            await assert.rejects(db.exec(`select * from public.${table}`))
        }
        await assert.rejects(db.exec('select public.internal_document_claim()'))
        await db.exec('reset role')
    }
    await db.exec('set role service_role')
    const actor = '00000000-0000-4000-8000-000000000001'
    const ids = ['00000000-0000-4000-8000-000000000011', '00000000-0000-4000-8000-000000000012', '00000000-0000-4000-8000-000000000013']
    async function insert(id, hash) {
        await db.query("insert into internal_documents(id,title,document_kind,effective_date,sha256,object_key,created_by) values($1,'Synthetic document','allocation','2020-01-01',$2,$3,$4)", [id, hash, `${id}.hwp`, actor])
    }
    async function action(id, input) { return db.query('select internal_document_action($1,$2,$3::jsonb)', [id, actor, JSON.stringify(input)]) }
    async function row(id) { return (await db.query('select * from internal_documents where id=$1',[id])).rows[0] }
    async function claim() { return (await db.query('select internal_document_claim() as job')).rows[0].job }
    async function finish(job, error = null) {
        return db.query('select internal_document_finish($1,$2,$3::jsonb,$4::jsonb,$5)', [job.document_id, job.lease_token, JSON.stringify([{ article_key: '1', heading: 'Synthetic team', department: 'Synthetic team', body: 'Synthetic duty', start_paragraph: 1, end_paragraph: 2 }]), '[]', error])
    }
    await insert(ids[0], 'a'.repeat(64))
    await assert.rejects(action(ids[0], { action: 'delete', revision: 0 })) // in-flight upload
    await db.query('select internal_document_enqueue($1,$2)', [ids[0], actor])
    let job = await claim()
    assert.equal(job.document_id, ids[0])
    assert.equal(await claim(), null) // lease prevents duplicate processing
    await assert.rejects(db.query('select internal_document_finish($1,$2,$3,$4,$5)', [ids[0], actor, '[]','[]',null]))
    await finish(job)
    let current = await row(ids[0])
    assert.equal(current.status, 'review')
    await assert.rejects(action(ids[0], { action: 'activate', revision: current.revision }))
    await action(ids[0], { action: 'review', revision: current.revision, units: [{ article_key: '1', department: 'Verified team', reviewed: true }], warnings_acknowledged: true })
    await assert.rejects(action(ids[0], { action: 'activate', revision: current.revision })) // optimistic lock
    current = await row(ids[0])
    await action(ids[0], { action: 'activate', revision: current.revision })
    assert.equal((await row(ids[0])).status, 'active')

    await insert(ids[1], 'b'.repeat(64))
    await db.query('select internal_document_enqueue($1,$2)', [ids[1], actor])
    await finish(await claim())
    current = await row(ids[1])
    await action(ids[1], { action: 'review', revision: current.revision, units: [{ article_key: '1', department: 'New team', reviewed: true }], warnings_acknowledged: true })
    await action(ids[1], { action: 'activate', revision: (await row(ids[1])).revision })
    assert.equal((await row(ids[0])).status, 'retired')
    await action(ids[1], { action: 'delete', revision: (await row(ids[1])).revision })
    for (let attempt = 0; attempt < 3; attempt++) {
        await db.exec("update internal_document_jobs set available_at=now()-interval '1 second'")
        job = await claim(); await finish(job, 'storage_failed')
    }
    assert.equal((await row(ids[1])).status, 'delete_failed')
    await action(ids[1], { action: 'delete', revision: (await row(ids[1])).revision })
    await finish(await claim())
    assert.equal((await row(ids[1])).status, 'deleted')
    assert.equal((await db.query('select * from internal_document_units where document_id=$1',[ids[1]])).rows.length, 0)
    await insert(ids[2], 'b'.repeat(64)) // deleted file can be registered again
    await db.query("update internal_documents set created_at=now()-interval '16 minutes' where id=$1",[ids[2]])
    await action(ids[2], { action: 'delete', revision: 0 }) // abandoned upload recovery
    job = await claim()
    await db.query("update internal_document_jobs set attempts=3,lease_until=now()-interval '1 second' where document_id=$1",[ids[2]])
    assert.equal(await claim(), null)
    assert.equal((await row(ids[2])).status, 'delete_failed')
    await action(ids[2], { action: 'delete', revision: (await row(ids[2])).revision })
    assert.equal((await row(ids[2])).error_code, null)
    await claim()
    await db.query("update internal_document_jobs set attempts=3,lease_until=now()-interval '1 second' where document_id=$1",[ids[2]])
    await claim()
    assert.equal((await row(ids[2])).status, 'delete_failed')
    await action(ids[2], { action: 'delete', revision: (await row(ids[2])).revision })
    await finish(await claim())
    assert.equal((await row(ids[2])).status, 'deleted')
    assert.equal((await db.query("select internal_admin_rate_limit('fixture',1,60) as allowed")).rows[0].allowed, true)
    assert.equal((await db.query("select internal_admin_rate_limit('fixture',1,60) as allowed")).rows[0].allowed, false)
    await db.close()
    console.log('PASS: migration, private privileges/RLS, lease, review, activation, version replacement, deletion recovery, re-upload, rate limits')
}
main().catch(error => { console.error(error); process.exitCode = 1 })
