"""Frozen upstream structure plus native READ ONLY retained Source audit."""
import hashlib,json,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
import psycopg
from psycopg.rows import dict_row
R=Path(__file__).resolve().parents[2];B=Path(__file__).resolve().parent
sys.path.insert(0,str(R/'services/aos-api'))
from aos_api.aip_provider_capacity_publication_transaction import require_source_transaction_functions
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
for x in json.loads((B/'inputs.json').read_text()):assert sha(R/x['path'])==x['sha256']
source=(B/'upstream-xact.c').read_text();lines=source.splitlines()
def body(name):
    start=source.index('\n'+name+'(')
    brace=source.index('{',start);depth=0
    for offset in range(brace,len(source)):
        if source[offset]=='{':depth+=1
        if source[offset]=='}':
            depth-=1
            if depth==0:return source[start:offset+1]
    raise AssertionError(name)
def ordered(name,anchors):
    text=body(name);positions=[text.index(a) for a in anchors]
    assert positions==sorted(positions) and len(set(positions))==len(positions)
    base=source.index(text)
    return [{'anchor':a,'line':source[:base+i].count('\n')+1} for a,i in zip(anchors,positions)]
pipeline=ordered('CommitTransaction',['AfterTriggerFireDeferred();','PreCommit_Portals(false)','XACT_EVENT_PRE_COMMIT','AtEOXact_Parallel(true)','PreCommit_on_commit_actions();','smgrDoPendingSyncs(true','PreCommit_Notify();','PreCommit_CheckForSerializationFailure();','HOLD_INTERRUPTS();','RecordTransactionCommit();','XACT_EVENT_COMMIT'])
wal=ordered('RecordTransactionCommit',['START_CRIT_SECTION();','XactLogCommitRecord(GetCurrentTransactionStopTimestamp()','XLogFlush(XactLastRecEnd);','TransactionIdCommitTree(xid','SyncRepWaitForLSN(XactLastRecEnd, true)'])
registration=ordered('RegisterXactCallback',['item->next = Xact_callbacks;','Xact_callbacks = item;'])
callbacks=body('CallXactCallbacks');assert 'item = Xact_callbacks' in callbacks and 'item = next' in callbacks and 'next = item->next;' in callbacks and 'item->callback(event, item->arg);' in callbacks
prepare=body('PrepareTransaction');assert 'XACT_EVENT_PRE_PREPARE' in prepare and 'XACT_EVENT_PRE_COMMIT' not in prepare
full=R/'.evidence/gt-source-desktop-shm-lab-20261009'
proof=json.loads((full/'independent-whole-final-verification.json').read_text());lab=json.loads((full/'lab.json').read_text())
database=next(x['database'] for x in proof['databases'] if x['sources'])
with psycopg.connect(host='127.0.0.1',port=lab['port'],dbname=database,user='aos_app',passfile=lab['passfile'],row_factory=dict_row) as c:
    c.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ ONLY')
    settings={k:c.execute('SHOW '+k).fetchone()[k] for k in ('transaction_read_only','transaction_isolation','server_version','fsync','full_page_writes','synchronous_commit','shared_preload_libraries','session_preload_libraries','local_preload_libraries','max_prepared_transactions','synchronous_standby_names','commit_delay')}
    assert settings['transaction_read_only']=='on' and settings['transaction_isolation']=='serializable'
    assert all(settings[k]=='on' for k in ('fsync','full_page_writes','synchronous_commit'))
    assert settings['server_version'].startswith('16.14')
    assert c.execute('SELECT system_identifier::text AS id FROM pg_control_system()').fetchone()['id']==lab['cluster']
    require_source_transaction_functions(c)
    rows=c.execute("""SELECT p.asset_id,p.content_hash,p.content_hash=encode(sha256(p.source_raw),'hex') AS hash_ok,
       aos_ed25519.verify(p.signature,p.source_raw,decode(s.signed_facts->>'sourceSignerPublicKey','base64')) AS signature_ok,
       s.finalized,v.native_xid::text AS xid,v.native_session,
       v.native_xid=s.native_xid AND v.native_pid=s.native_pid AND v.original_signed_facts=s.signed_facts AS provenance_ok
       FROM aos_capacity_publication_private.source_publication p JOIN aos_capacity_publication_private.source_pending s ON s.attempt_id=p.attempt_id
       JOIN aos_capacity_publication_private.source_provenance v ON (v.org_id,v.project_id,v.asset_id)=(p.org_id,p.project_id,p.asset_id)""").fetchall()
    for row in rows:
        assert all(row[k] for k in ('hash_ok','signature_ok','finalized','provenance_ok'))
        row['xid_status']=c.execute('SELECT pg_xact_status(%s::xid8) AS state',(row['xid'],)).fetchone()['state'];assert row['xid_status']=='committed'
    assert rows
    triggers=c.execute("""SELECT t.tgname,t.tgdeferrable,t.tginitdeferred,pg_get_triggerdef(t.oid) AS definition,
       encode(sha256(convert_to(pg_get_functiondef(t.tgfoid),'UTF8')),'hex') AS function_sha256
       FROM pg_trigger t JOIN pg_class r ON r.oid=t.tgrelid JOIN pg_namespace n ON n.oid=r.relnamespace
       WHERE n.nspname='aos_capacity_publication_private' ORDER BY r.relname,t.tgname""").fetchall()
    interfaces={fn:c.execute('SELECT to_regprocedure(%s) IS NULL AS absent',(fn,)).fetchone()['absent'] for fn in ('public.prepare_capacity_source(bytea,text,text,jsonb)','public.commit_capacity_source(text,bytea,bytea)')}
    assert all(interfaces.values())
result=dict(observed_at=datetime.now(timezone.utc).isoformat(),head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),authority_revision='AOS-001649',upstream_url='https://raw.githubusercontent.com/postgres/postgres/REL_16_14/src/backend/access/transam/xact.c',upstream_sha256=sha(B/'upstream-xact.c'),commit_pipeline=pipeline,wal_pipeline=wal,callback_registration=registration,callback_order='LIFO; another earlier-registered callback can run after deadline callback',prepare_requires_separate_gate=True,native_database=database,native_cluster=lab['cluster'],settings=settings,retained_sources=rows,source_triggers=triggers,temporary_interfaces_absent=interfaces,read_only=True,inputs_unchanged=True,strict_completion_deadline='RED_UNPROVEN',precommit_callback_installed=False,source_or_business_delivery=False)
(B/'boundary-audit.json').write_text(json.dumps(result,indent=2))
print('READ_ONLY_OK; ordered commit/WAL/prepare/callback audit; retained signed Source committed; strict completion deadline RED_UNPROVEN')
