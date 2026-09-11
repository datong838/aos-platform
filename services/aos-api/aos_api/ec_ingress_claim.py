"""Claim only a stopped failed ingress with its original saved input."""
import json
from datetime import datetime
from uuid import UUID
from psycopg import sql
from aos_api.ec_ingress_journal import IngressJournalConflict, _digest


def claim_failed_run(connection_factory, scope, run_id, claim_id, *, journal):
    if str(UUID(claim_id)) != claim_id:
        raise ValueError('INGRESS_CLAIM_ID_INVALID')
    claims=sql.Identifier(journal.schema,'ecommerce_ingress_recovery_claim')
    runs=sql.Identifier(journal.schema,'meta_schedule_run')
    with connection_factory(scope) as conn:
        with conn.transaction():
            journal.lock_run(conn,scope,run_id)
            parent=journal.read(conn,scope,run_id)
            if parent is None:
                raise IngressJournalConflict('INGRESS_PARENT_REQUIRED')
            prior=conn.execute(sql.SQL('SELECT payload,payload_hash FROM {} WHERE org_id=%s AND project_id=%s AND run_id=%s AND claim_id=%s').format(claims),(*scope.key,run_id,claim_id)).fetchone()
            if prior is not None:
                if _digest(prior['payload']) != prior['payload_hash'] or prior['payload'].get('parentHash') != _digest(parent):
                    raise IngressJournalConflict('INGRESS_CLAIM_DRIFT')
                return False
            run=conn.execute(sql.SQL('SELECT * FROM {} WHERE org_id=%s AND project_id=%s AND id=%s FOR UPDATE').format(runs),(*scope.key,run_id)).fetchone()
            if run is None or run['status']!='failed' or run['executor_stopped'] is not True or run['finished_at'] is None:
                raise IngressJournalConflict('INGRESS_STOPPED_FAILED_RUN_REQUIRED')
            def encode(value):
                if isinstance(value,datetime):
                    return value.isoformat()
                raise TypeError('INGRESS_CLAIM_VALUE_INVALID')
            snapshot=json.loads(json.dumps(dict(run),default=encode,allow_nan=False))
            payload={'parentHash':_digest(parent),'previousRun':snapshot}
            conn.execute(sql.SQL('INSERT INTO {}(org_id,project_id,run_id,claim_id,payload_hash,payload) VALUES(%s,%s,%s,%s,%s,%s::jsonb)').format(claims),
                         (*scope.key,run_id,claim_id,_digest(payload),json.dumps(payload,ensure_ascii=False,allow_nan=False)))
            conn.execute(sql.SQL("UPDATE {} SET status='running',executor_stopped=false,finished_at=NULL WHERE org_id=%s AND project_id=%s AND id=%s").format(runs),(*scope.key,run_id))
            journal.verify_running_schedule(conn,scope,run_id=run_id,pipeline_id=parent['pipelineId'],source_id=parent['sourceId'],
                                            source_revision=parent['sourceRevision'],pipeline_hash=parent['pipelineHash'])
    return True
