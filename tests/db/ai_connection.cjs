const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { PGlite } = require(require.resolve('@electric-sql/pglite', { paths: [path.join(__dirname, '../../web')] }))
async function main() {
 const db = new PGlite()
 await db.exec('create role anon; create role authenticated; create role service_role bypassrls;')
 await db.exec(fs.readFileSync(path.join(__dirname, '../../db/migrations/202611020001_ai_connection.sql'), 'utf8'))
 const sql = 'select sanction_ai_connection_save($1,$2,$3,$4,$5,$6,$7) as revision'
 const input = [0,'https://fixture.test/v1','responses','fixture-model','v1.'+'synthetic'.repeat(10),'test','00000000-0000-4000-8000-000000000001']
 for (const role of ['anon','authenticated']) {
  await db.exec(`set role ${role}`)
  await assert.rejects(db.exec('select * from sanction_ai_connection'))
  await assert.rejects(db.query(sql,input))
  await db.exec('reset role')
 }
 await db.exec('set role service_role')
 assert.equal((await db.query(sql,input)).rows[0].revision,1)
 await assert.rejects(db.query(sql,input))
 const before = (await db.exec('select * from sanction_ai_connection'))[0].rows
 await assert.rejects(db.query(sql,[1,input[1],'wrong',...input.slice(3)]))
 assert.deepEqual((await db.exec('select * from sanction_ai_connection'))[0].rows,before)
 assert.equal((await db.query(sql,[1,...input.slice(1)])).rows[0].revision,2)
 assert.equal((await db.exec('select count(*) as n from sanction_ai_connection'))[0].rows[0].n,1)
 await db.close(); console.log('AI connection DB checks passed')
}
main().catch(error => { console.error(error); process.exit(1) })
