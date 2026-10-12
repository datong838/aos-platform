"""Caller-owned, bounded atomic ending; never starts or admits a producer."""
from psycopg import sql
from psycopg.rows import dict_row

from aos_api.aip_eval_authority_store import AipEvalAuthorityStore
from aos_api.aip_eval_contracts import EvalRunStatus
from aos_api.aip_eval_execution_authority import EvalExecutionRejected
from aos_api.aip_eval_writer_atomic import _persist_signed_skill_eval_report_with_connection
from aos_api.aip_skill_eval_producer_identity import require_skill_producer_identity


def _require(ok, reason):
    if not ok:
        raise EvalExecutionRejected(reason)


def _bounded_finisher(conn):
    # Effective privileges include PUBLIC and inherited grants. The old writer
    # and login must not acquire the finishing capability indirectly.
    rows = conn.execute("""SELECT attname,
        has_column_privilege('aos_skill_eval_finisher',attrelid,attnum,'UPDATE') AS finish_update,
        has_column_privilege('aos_aip_eval_writer',attrelid,attnum,'UPDATE') AS writer_update,
        has_column_privilege(session_user,attrelid,attnum,'UPDATE') AS login_update
        FROM pg_catalog.pg_attribute WHERE attrelid='public.aip_eval_run'::regclass
        AND attnum>0 AND NOT attisdropped""").fetchall()
    _require({r['attname'] for r in rows if r['finish_update']} ==
             {'status', 'version', 'started_at', 'finished_at'}
             and not any(r['writer_update'] or r['login_update'] for r in rows),
             'Skill finisher Run capabilities are not bounded')
    row = conn.execute("""SELECT
        has_table_privilege('aos_skill_eval_finisher','public.aip_eval_run','SELECT') AS run_read,
        has_table_privilege('aos_skill_eval_finisher','public.aip_eval_run','INSERT,UPDATE,DELETE,TRUNCATE,REFERENCES,TRIGGER') AS run_wide,
        has_table_privilege('aos_skill_eval_finisher','public.aip_eval_run_event','SELECT') AS event_read,
        has_table_privilege('aos_skill_eval_finisher','public.aip_eval_run_event','INSERT') AS event_insert,
        has_any_column_privilege('aos_skill_eval_finisher','public.aip_eval_run_event','UPDATE') AS event_update,
        has_table_privilege('aos_skill_eval_finisher','public.aip_eval_run_event','DELETE,TRUNCATE,REFERENCES,TRIGGER') AS event_wide""").fetchone()
    _require(row['run_read'] and not row['run_wide'] and row['event_read']
             and row['event_insert'] and not row['event_update'] and not row['event_wide'],
             'Skill finisher event capabilities are not bounded')


def _observed_dispatches(conn, scope, intent_id, report, inputs, presented):
    rows = conn.execute("""SELECT d.case_id,d.purpose,d.input_hash,d.created_at,
        o.observed_at,o.result_hash FROM aip_skill_eval_dispatch d
        LEFT JOIN aip_skill_eval_dispatch_observation o
        ON o.org_id=d.org_id AND o.project_id=d.project_id
        AND o.dispatch_id=d.dispatch_id AND o.state='result_observed'
        WHERE d.org_id=%s AND d.project_id=%s AND d.intent_id=%s""",
        (*scope.key,intent_id)).fetchall()
    expected = {(r.case_id,p) for r in report.results for p in ('target','judge')}
    indexed = {(r['case_id'],r['purpose']):r for r in rows}
    _require(len(rows)==len(expected) and set(indexed)==expected
             and set(inputs)==set(presented)=={r.case_id for r in report.results},
             'Skill ending dispatch set is incomplete')
    for result in report.results:
        pair = presented[result.case_id]
        for purpose,receipt in (('target',pair.target_receipt),('judge',pair.judge_receipt)):
            row = indexed[(result.case_id,purpose)]
            _require(receipt.purpose==purpose and row['observed_at'] is not None
                and row['input_hash']==receipt.input_hash==inputs[result.case_id]
                and row['result_hash']==receipt.output_hash
                and row['created_at']<=receipt.occurred_at<=row['observed_at']<=report.created_at,
                'Skill ending observation or signed receipt drifted')
        _require(indexed[(result.case_id,'target')]['observed_at']<=
                 indexed[(result.case_id,'judge')]['created_at'],
                 'Skill Judge dispatch preceded observed Target')


def finish_signed_skill_eval_with_connection(conn, *, expected_database, scope,
    intent_id, expected_intent_version, request_hash, event, expected_run_version,
    report, expected_input_hashes, presented):
    """Finish a new admitted Run without committing or retrying the caller.

    The caller must already hold formal producer admission. A returned proof is
    local to this transaction; commit uncertainty requires read-only recovery.
    The savepoint prevents a caught late error from leaving a false success.
    """
    _require(conn.autocommit is False and conn.row_factory is dict_row,
             'caller-owned Skill ending transaction required')
    require_skill_producer_identity(conn,expected_database=expected_database)
    context = conn.execute("""SELECT session_user AS login,
        current_setting('transaction_isolation') AS isolation,
        current_setting('transaction_read_only') AS readonly,
        transaction_timestamp() AS evaluated_at,
        current_setting('aos.org_id',true) AS org_id,
        current_setting('aos.project_id',true) AS project_id""").fetchone()
    _require(context['isolation']=='serializable' and context['readonly']=='off'
             and (context['org_id'],context['project_id'])==scope.key
             and (report.tenant.org_id,report.tenant.project_id)==scope.key
             and event.tenant==report.tenant and event.run_id==report.run_id
             and event.from_status is EvalRunStatus.RUNNING
             and event.to_status is EvalRunStatus.SUCCEEDED
             and event.event_type=='run.succeeded'
             and type(expected_run_version) is int and expected_run_version>=1
             and event.created_at.utcoffset() is not None
             and report.created_at.utcoffset() is not None
             and report.created_at<=event.created_at<=context['evaluated_at']
             and event.payload_hash==report.content_hash,
             'Skill ending tenant, event or transaction drifted')
    _bounded_finisher(conn)
    with conn.transaction():
        conn.execute('SET LOCAL search_path TO pg_catalog,public')
        conn.execute('SET LOCAL ROLE aos_aip_eval_writer')
        intent = conn.execute("""SELECT * FROM aip_skill_eval_intent
            WHERE org_id=%s AND project_id=%s AND intent_id=%s FOR UPDATE""",
            (*scope.key,intent_id)).fetchone()
        _require(intent is not None and type(expected_intent_version) is int
                 and intent['version']==expected_intent_version
                 and intent['run_id']==report.run_id and intent['request_hash']==request_hash,
                 'Skill ending intent version or request drifted')
        _observed_dispatches(conn,scope,intent_id,report,expected_input_hashes,presented)
        conn.execute('SET LOCAL ROLE aos_skill_eval_finisher')
        AipEvalAuthorityStore()._transition_eval_run_with_connection(
            conn,scope,event,expected_version=expected_run_version)
        conn.execute('SET LOCAL ROLE aos_aip_eval_writer')
        proof = _persist_signed_skill_eval_report_with_connection(conn,report=report,
            expected_input_hashes=expected_input_hashes,presented=presented)
        updated = conn.execute("""UPDATE aip_skill_eval_intent SET version=version+1
            WHERE org_id=%s AND project_id=%s AND intent_id=%s AND version=%s
            RETURNING intent_id""",(*scope.key,intent_id,expected_intent_version)).fetchone()
        _require(updated is not None,'Skill ending intent changed concurrently')
        conn.execute(sql.SQL('SET LOCAL ROLE {}').format(sql.Identifier(context['login'])))
    return proof
