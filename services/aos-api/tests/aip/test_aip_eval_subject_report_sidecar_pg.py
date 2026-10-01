"""Disposable PostgreSQL proof for exact Subject Receipt -> Report FKs."""
import os

import psycopg
import pytest
from psycopg.types.json import Jsonb

from aos_api.aip_eval_subject_proof_authority import claim_hash
from test_aip_eval_subject_persisted_reader_pg import _json, _seed
from test_aip_eval_subject_signature import NOW, pair


def _connect():
    conn=psycopg.connect(os.environ['AOS_DATABASE_URL'])
    assert conn.info.dbname.startswith('aos_test_') and conn.info.dbname.endswith('_ti4_test')
    return conn


def _report(conn, envelope):
    conn.execute("""INSERT INTO aip_eval_report_revision
        (org_id,project_id,report_id,revision,content_hash,run_id,suite_ref,
         target_ref,dataset_ref,judge_ref,results,passed,failed,total,pass_rate,
         gate_passed,created_at,eval_contract_ref,subject_artifact_ref,
         stage_attempt_ref,gate_policy_ref,evidence_cutoff_at)
        VALUES ('org-org','dev-project','subject-report',1,%s,%s,%s,%s,%s,%s,
                %s,1,0,1,1.0,true,%s,%s,%s,%s,%s,%s)""",
        ('e'*64,envelope.eval_run_id,_json(envelope.suite_ref),
         _json(envelope.generation_skill_ref),Jsonb({'testOnly':True}),
         _json(envelope.judge_ref),Jsonb([{'caseId':envelope.case_id,'passed':True}]),
         NOW,_json(envelope.contract_ref),_json(envelope.subject_artifact_ref),
         _json(envelope.stage_attempt_ref),_json(envelope.policy_ref),envelope.cutoff))


def _insert(conn,envelope,signed,**overrides):
    source,judge=(pair[1] for pair in signed)
    fields=dict(org_id='org-org',project_id='dev-project',eval_run_id=envelope.eval_run_id,
        case_id=envelope.case_id,envelope_hash=source.envelope_hash,report_id='subject-report',
        report_revision=1,source_receipt_id=source.receipt_id,source_claim_hash=claim_hash(source),
        judge_receipt_id=judge.receipt_id,judge_claim_hash=claim_hash(judge),verified_at=NOW,
        created_at=NOW)
    fields.update(overrides)
    conn.execute("""INSERT INTO aip_eval_subject_case_proof
        (org_id,project_id,eval_run_id,case_id,envelope_hash,report_id,
         report_revision,source_receipt_id,source_claim_hash,judge_receipt_id,
         judge_claim_hash,verified_at,created_at)
        VALUES (%(org_id)s,%(project_id)s,%(eval_run_id)s,%(case_id)s,
                %(envelope_hash)s,%(report_id)s,%(report_revision)s,
                %(source_receipt_id)s,%(source_claim_hash)s,%(judge_receipt_id)s,
                %(judge_claim_hash)s,%(verified_at)s,%(created_at)s)""",fields)


def test_subject_report_sidecar_schema_and_runtime_read_only():
    with _connect() as conn:
        assert conn.execute('SELECT version_num FROM alembic_version').fetchone()==('a0v_132',)
        table='aip_eval_subject_case_proof'
        acl=conn.execute('''SELECT has_table_privilege('aos_runtime',%s,'SELECT'),
            has_table_privilege('aos_runtime',%s,'INSERT'),
            has_table_privilege('aos_runtime',%s,'UPDATE'),
            has_table_privilege('aos_runtime',%s,'DELETE'),
            has_table_privilege('aos_runtime',%s,'TRUNCATE')''',(table,)*5).fetchone()
        assert acl==(True,False,False,False,False)
        assert conn.execute("""SELECT relrowsecurity,relforcerowsecurity
            FROM pg_class WHERE oid='aip_eval_subject_case_proof'::regclass""").fetchone()==(True,True)
        constraints=[r[0] for r in conn.execute("""SELECT pg_get_constraintdef(oid)
            FROM pg_constraint WHERE conrelid='aip_eval_subject_case_proof'::regclass""")]
        assert any('report_id' in row and 'FOREIGN KEY' in row for row in constraints)
        assert sum('receipt_id' in row and 'FOREIGN KEY' in row for row in constraints)==2
        triggers={r[0] for r in conn.execute("""SELECT tgname FROM pg_trigger
            WHERE tgrelid='aip_eval_subject_case_proof'::regclass AND NOT tgisinternal""")}
        assert any('append_only' in name for name in triggers)
        assert any('truncate_guard' in name for name in triggers)


@pytest.mark.parametrize('fault',['valid','missing_report','wrong_report','wrong_source',
    'wrong_judge','wrong_envelope','cross_tenant'])
def test_subject_sidecar_binds_one_exact_report_and_both_receipts(fault):
    with _connect() as conn:
        envelope,root,signed,_=pair()
        _seed(conn,envelope,root,signed)
        if fault!='missing_report': _report(conn,envelope)
        overrides={
            'wrong_report':{'report_id':'other'},
            'wrong_source':{'source_claim_hash':'0'*64},
            'wrong_judge':{'judge_claim_hash':'0'*64},
            'wrong_envelope':{'envelope_hash':'0'*64},
            'cross_tenant':{'org_id':'dev-org'},
        }.get(fault,{})
        if fault=='valid':
            _insert(conn,envelope,signed)
            conn.execute('SET LOCAL ROLE aos_runtime')
            conn.execute("SELECT set_config('aos.org_id','org-org',true)")
            conn.execute("SELECT set_config('aos.project_id','dev-project',true)")
            assert conn.execute('SELECT count(*) FROM aip_eval_subject_case_proof').fetchone()==(1,)
            conn.execute("SELECT set_config('aos.org_id','dev-org',true)")
            assert conn.execute('SELECT count(*) FROM aip_eval_subject_case_proof').fetchone()==(0,)
        else:
            with pytest.raises(psycopg.Error),conn.transaction():
                _insert(conn,envelope,signed,**overrides)
        conn.rollback()
