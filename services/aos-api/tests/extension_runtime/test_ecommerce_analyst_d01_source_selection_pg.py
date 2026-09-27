"""D01 selection storage must be inert without its checked write functions."""
import pytest
import psycopg
from psycopg.types.json import Jsonb
from uuid import uuid4

from aos_api.db import connect, connect_platform, connect_serializable
from aos_api.ecommerce_analyst_authority_store import canonical_hash
from aos_api.ecommerce_analyst_d01_source_selection import D01SourceSelectionProposal
from aos_api.ecommerce_analyst_d01_source_selection_store import D01SourceSelectionStore
from aos_api.ecommerce_growth_host_ports import HostTransaction
from aos_api.tenant_scope import TenantScope
from test_ecommerce_analyst_d01_issuer import _packet, _request


TABLES = (
    'ecommerce_d01_source_proposal',
    'ecommerce_d01_source_approval',
    'ecommerce_d01_source_revocation',
)


@pytest.mark.parametrize('table', TABLES)
def test_selection_history_is_scoped_immutable_and_not_directly_writable(table):
    with connect_platform() as conn:
        row = conn.execute(
            """SELECT c.relrowsecurity AS rls,c.relforcerowsecurity AS forced,
                      has_table_privilege('aos_runtime',c.oid,'SELECT') AS readable,
                      has_table_privilege('aos_runtime',c.oid,'INSERT') AS insertable,
                      has_table_privilege('aos_runtime',c.oid,'UPDATE') AS updatable,
                      has_table_privilege('aos_runtime',c.oid,'DELETE') AS deletable
               FROM pg_class c WHERE c.oid=to_regclass(%s)""",
            ('public.' + table,),
        ).fetchone()
        assert row is not None
        assert row == dict(rls=True, forced=True, readable=True,
                           insertable=False, updatable=False, deletable=False)
        triggers = conn.execute(
            """SELECT tgname FROM pg_trigger
               WHERE tgrelid=to_regclass(%s) AND NOT tgisinternal""",
            ('public.' + table,),
        ).fetchall()
        assert {item['tgname'] for item in triggers} == {
            table + '_immutable_row', table + '_immutable_truncate',
        }


def test_runtime_cannot_insert_a_proposal_behind_the_decision_owner():
    scope = TenantScope('dev-org', 'dev-project')
    with connect(scope) as conn, pytest.raises(psycopg.errors.InsufficientPrivilege):
        conn.execute(
            """INSERT INTO ecommerce_d01_source_proposal
              (org_id,project_id,selection_id,task_run_id,plan_revision_id,
               plan_content_hash,source_selection_ref,packet,proposal_key,
               request_hash,content_hash,maker,proposed_at)
              VALUES (%s,%s,'forbidden','none','none',%s,'{}','{}',
                      'forbidden',%s,%s,'tester',clock_timestamp())""",
            (*scope.key, 'a' * 64, 'a' * 64, 'a' * 64),
        )


def test_checked_proposal_function_is_the_only_runtime_write_route():
    signature = ('public.ecommerce_d01_source_propose_a0v_107('
                 'text,text,text,text,jsonb,jsonb,jsonb,text,text,text,text,timestamptz)')
    with connect_platform() as conn:
        row = conn.execute(
            """SELECT to_regprocedure(%s) IS NOT NULL AS present,
               has_function_privilege('aos_runtime',to_regprocedure(%s),'EXECUTE')
                 AS runtime_execute""",
            (signature, signature),
        ).fetchone()
        assert row == dict(present=True, runtime_execute=True)


@pytest.mark.parametrize('signature', [
    'public.ecommerce_d01_source_approve_a0v_107(text,text,text,text,text,timestamptz)',
    'public.ecommerce_d01_source_revoke_a0v_107(text,text,text,text,text,timestamptz)',
])
def test_approval_and_revocation_have_checked_owner_functions(signature):
    with connect_platform() as conn:
        row = conn.execute(
            """SELECT to_regprocedure(%s) IS NOT NULL AS present,
               has_function_privilege('aos_runtime',to_regprocedure(%s),'EXECUTE')
                 AS runtime_execute""",
            (signature, signature),
        ).fetchone()
        assert row == dict(present=True, runtime_execute=True)


def test_checked_proposal_is_idempotent_and_same_run_payload_cannot_drift():
    scope = TenantScope('org-org', 'dev-project')
    suffix = uuid4().hex[:12]
    task_id, plan_id, run_id = ('d01-task-' + suffix, 'd01-plan-' + suffix,
                                'd01-run-' + suffix)
    source_ref = {'resourceType': 'SourceSelectionRevision',
                  'resourceId': 'source-' + suffix, 'revision': 1,
                  'contentHash': 'sha256:' + 'a' * 64}
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated') ON CONFLICT DO NOTHING")
        conn.execute("""INSERT INTO twa_workspace(org_id,project_id,name)
             VALUES('org-org','dev-project','isolated') ON CONFLICT DO NOTHING""")
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','isolated') ON CONFLICT DO NOTHING")
        conn.execute("""INSERT INTO meta_workspace(org_id,project_id,name)
             VALUES('org-org','dev-project','isolated') ON CONFLICT DO NOTHING""")
        conn.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
             VALUES('org-org','dev-project',%s,'analyst') ON CONFLICT DO NOTHING""",
             ('d01-maker-' + suffix,))
        conn.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
             VALUES('org-org','dev-project',%s,'approver') ON CONFLICT DO NOTHING""",
             ('d01-checker-' + suffix,))
        conn.execute("""INSERT INTO aip_task
             (org_id,project_id,task_id,task_type,title,status,selection_ref,
              idempotency_key,request_hash,current_plan_revision_id,created_by)
             VALUES(%s,%s,%s,'analysis','isolated D01','executing',%s,
                    %s,%s,%s,%s)""",
             (*scope.key, task_id, Jsonb({'resourceType':'SourceSelectionRevision',
                 'resourceId':source_ref['resourceId'],'revision':'1',
                 'authority':'postgresql'}), 'task-'+suffix, 'a'*64, plan_id,
                 'd01-maker-'+suffix))
        conn.execute("""INSERT INTO aip_plan_revision
             (org_id,project_id,plan_revision_id,task_id,revision,content_hash,
              steps,approval_status,idempotency_key,request_hash,created_by,
              approved_by,approved_at)
             VALUES(%s,%s,%s,%s,1,%s,%s,'approved',%s,%s,%s,%s,clock_timestamp())""",
             (*scope.key, plan_id, task_id, 'a'*64, Jsonb([{'stepKey':'portrait',
                 'inputRefs':[{'resourceType':'MethodRevision',
                 'resourceId':'method-1','revision':'1','authority':'postgresql'}]}]),
              'plan-'+suffix, 'a'*64, 'd01-maker-'+suffix, 'd01-checker-'+suffix))
        conn.execute("""INSERT INTO aip_task_run
             (org_id,project_id,run_id,task_id,plan_revision_id,status,
              idempotency_key,request_hash,created_by)
             VALUES(%s,%s,%s,%s,%s,'running',%s,%s,%s)""",
             (*scope.key, run_id, task_id, plan_id, 'run-'+suffix, 'a'*64,
              'd01-maker-'+suffix))
        conn.commit()

    proposal_id = 'd01-source-' + suffix
    key = 'proposal-' + suffix
    packet = _packet().model_dump(mode='json', by_alias=True)
    with connect_serializable(scope) as conn:
        conn.execute("SELECT set_config('aos.subject',%s,true)", ('d01-maker-'+suffix,))
        proposed_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        payload = {
            'tenant': {'orgId':scope.org_id,'projectId':scope.project_id},
            'taskRunRef': {'resourceType':'TaskRun','resourceId':run_id,
                           'revision':'1','authority':'postgresql'},
            'planRef': {'resourceType':'PlanRevision','resourceId':plan_id,
                        'revision':'1','authority':'postgresql'},
            'planContentHash':'a'*64, 'sourceSelectionRef':source_ref,
            'packet':packet,'proposedBy':'d01-maker-'+suffix,
            'proposedAt':proposed_at.isoformat(),
        }
        args = (proposal_id, run_id, plan_id, 'a'*64, Jsonb(source_ref),
                Jsonb(packet), Jsonb(payload), key, 'b'*64, 'c'*64,
                'd01-maker-'+suffix, proposed_at)
        first = conn.execute("""SELECT public.ecommerce_d01_source_propose_a0v_107(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS receipt""", args).fetchone()['receipt']
        replay = conn.execute("""SELECT public.ecommerce_d01_source_propose_a0v_107(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) AS receipt""", args).fetchone()['receipt']
        assert replay == first and first['resourceId'] == proposal_id
        with pytest.raises(psycopg.errors.UniqueViolation), conn.transaction():
            drift = (*args[:9], 'd'*64, *args[10:])
            conn.execute("""SELECT public.ecommerce_d01_source_propose_a0v_107(
                %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", drift)
        approved_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("""SELECT public.ecommerce_d01_source_approve_a0v_107(
                %s,%s,%s,%s,%s,%s)""",
                (proposal_id, 'approval-'+suffix, 'd'*64, 'c'*64,
                 'd01-maker-'+suffix, approved_at))
        conn.execute("SELECT set_config('aos.subject',%s,true)", ('d01-checker-'+suffix,))
        approval_args = (proposal_id, 'approval-'+suffix, 'd'*64, 'c'*64,
                         'd01-checker-'+suffix, approved_at)
        with pytest.raises(psycopg.errors.CheckViolation), conn.transaction():
            conn.execute("""SELECT public.ecommerce_d01_source_approve_a0v_107(
                %s,%s,%s,%s,%s,%s)""", approval_args)
        conn.commit()
    with connect_serializable(TenantScope('dev-org', 'dev-project')) as conn:
        assert conn.execute("""SELECT count(*) AS n FROM ecommerce_d01_source_proposal
            WHERE selection_id=%s""", (proposal_id,)).fetchone()['n'] == 0
    with connect_serializable(scope) as conn:
        conn.execute("SELECT set_config('aos.subject',%s,true)", ('d01-checker-'+suffix,))
        approved_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        approval_args = (*approval_args[:5], approved_at)
        approved = conn.execute("""SELECT public.ecommerce_d01_source_approve_a0v_107(
            %s,%s,%s,%s,%s,%s) AS receipt""", approval_args).fetchone()['receipt']
        replay = conn.execute("""SELECT public.ecommerce_d01_source_approve_a0v_107(
            %s,%s,%s,%s,%s,%s) AS receipt""", approval_args).fetchone()['receipt']
        assert approved == replay and approved['resourceType'] == 'D01SourceSelectionApproval'
        conn.commit()
    with connect_serializable(scope) as conn:
        revoked_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        revoke_args = (proposal_id, 'revoke-'+suffix, 'e'*64,
                       'd01-checker-'+suffix, 'source withdrawn', revoked_at)
        conn.execute("SELECT set_config('aos.subject',%s,true)", ('d01-maker-'+suffix,))
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("""SELECT public.ecommerce_d01_source_revoke_a0v_107(
                %s,%s,%s,%s,%s,%s)""", (*revoke_args[:3], 'd01-maker-'+suffix,
                                          *revoke_args[4:]))
        conn.execute("SELECT set_config('aos.subject',%s,true)", ('d01-checker-'+suffix,))
        revoked = conn.execute("""SELECT public.ecommerce_d01_source_revoke_a0v_107(
            %s,%s,%s,%s,%s,%s) AS receipt""", revoke_args).fetchone()['receipt']
        replay = conn.execute("""SELECT public.ecommerce_d01_source_revoke_a0v_107(
            %s,%s,%s,%s,%s,%s) AS receipt""", revoke_args).fetchone()['receipt']
        assert revoked == replay and revoked['resourceType'] == 'D01SourceSelectionRevocation'
        assert conn.execute("""SELECT count(*) AS n FROM ecommerce_d01_source_revocation
            WHERE org_id=%s AND project_id=%s AND selection_id=%s""",
            (*scope.key, proposal_id)).fetchone()['n'] == 1
        conn.commit()

def test_real_two_stage_decision_is_read_in_same_transaction_and_revocation_closes_it():
    scope = TenantScope('org-org', 'dev-project')
    suffix = uuid4().hex[:12]
    task_id, plan_id, run_id = ('c-task-' + suffix, 'c-plan-' + suffix,
                                'c-run-' + suffix)
    maker, checker = 'c-maker-' + suffix, 'c-checker-' + suffix
    refs = [ref.model_dump(mode='json', by_alias=True)
            for ref in _request().run.input_refs]
    steps = [{'stepKey':'portrait','title':'业务画像','inputRefs':refs}]
    source_ref = {'resourceType':'SourceSelectionRevision',
                  'resourceId':'c-source-' + suffix,'revision':1,
                  'contentHash':'sha256:' + 'a' * 64}
    with connect() as conn:
        conn.execute("INSERT INTO twa_org(id,name) VALUES('org-org','isolated') ON CONFLICT DO NOTHING")
        conn.execute("""INSERT INTO twa_workspace(org_id,project_id,name)
             VALUES('org-org','dev-project','isolated') ON CONFLICT DO NOTHING""")
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','isolated') ON CONFLICT DO NOTHING")
        conn.execute("""INSERT INTO meta_workspace(org_id,project_id,name)
             VALUES('org-org','dev-project','isolated') ON CONFLICT DO NOTHING""")
        for subject, role in ((maker, 'analyst'), (checker, 'approver')):
            conn.execute("""INSERT INTO meta_membership(org_id,project_id,subject,role)
                 VALUES(%s,%s,%s,%s)""", (*scope.key, subject, role))
        conn.execute("""INSERT INTO aip_task
             (org_id,project_id,task_id,task_type,title,status,selection_ref,
              idempotency_key,request_hash,current_plan_revision_id,created_by)
             VALUES(%s,%s,%s,'analysis','isolated D01','executing',%s,
                    %s,%s,%s,%s)""",
             (*scope.key, task_id, Jsonb({'resourceType':'SourceSelectionRevision',
                 'resourceId':source_ref['resourceId'],'revision':'1',
                 'authority':'postgresql'}), 'c-task-'+suffix, 'a'*64, plan_id, maker))
        conn.execute("""INSERT INTO aip_plan_revision
             (org_id,project_id,plan_revision_id,task_id,revision,content_hash,
              steps,approval_status,idempotency_key,request_hash,created_by,
              approved_by,approved_at)
             VALUES(%s,%s,%s,%s,1,%s,%s,'approved',%s,%s,%s,%s,clock_timestamp())""",
             (*scope.key, plan_id, task_id, 'a'*64, Jsonb(steps),
              'c-plan-'+suffix, 'a'*64, maker, checker))
        conn.execute("""INSERT INTO aip_task_run
             (org_id,project_id,run_id,task_id,plan_revision_id,status,
              idempotency_key,request_hash,created_by)
             VALUES(%s,%s,%s,%s,%s,'running',%s,%s,%s)""",
             (*scope.key, run_id, task_id, plan_id, 'c-run-'+suffix, 'a'*64, maker))
        conn.commit()
    with connect_serializable(scope) as conn:
        proposed_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        proposal = D01SourceSelectionProposal.model_validate({
            'tenant':{'orgId':scope.org_id,'projectId':scope.project_id},
            'taskRunRef':{'resourceType':'TaskRun','resourceId':run_id,
                          'revision':'1','authority':'postgresql'},
            'planRef':{'resourceType':'PlanRevision','resourceId':plan_id,
                       'revision':'1','authority':'postgresql'},
            'planContentHash':'a'*64,'sourceSelectionRef':source_ref,
            'packet':_packet().model_dump(mode='json', by_alias=True),
            'proposedBy':maker,'proposedAt':proposed_at.isoformat(),
        })
        payload = proposal.model_dump(mode='json', by_alias=True)
        conn.execute("SELECT set_config('aos.subject',%s,true)", (maker,))
        conn.execute("""SELECT public.ecommerce_d01_source_propose_a0v_107(
            %s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (proposal.selection_id,run_id,plan_id,'a'*64,Jsonb(payload['sourceSelectionRef']),
             Jsonb(payload['packet']),Jsonb(payload),'c-proposal-'+suffix,
             canonical_hash({'key':'c-proposal-'+suffix,'proposal':payload}),
             canonical_hash(payload),maker,proposed_at))
        conn.commit()
    with connect_serializable(scope) as conn:
        approved_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        conn.execute("SELECT set_config('aos.subject',%s,true)", (checker,))
        conn.execute("""SELECT public.ecommerce_d01_source_approve_a0v_107(
            %s,%s,%s,%s,%s,%s)""",
            (proposal.selection_id,'c-approval-'+suffix,'b'*64,
             canonical_hash(payload),checker,approved_at))
        conn.commit()
    with connect_serializable(scope) as conn:
        now = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        packet, receipt = D01SourceSelectionStore().read_current(
            HostTransaction(conn), scope, run_id, plan_id, maker, now)
        assert packet == proposal.packet
        assert receipt['resourceType'] == 'D01SourceSelectionApproval'
    with connect_serializable(scope) as conn:
        revoked_at = conn.execute('SELECT clock_timestamp() AS now').fetchone()['now']
        conn.execute("SELECT set_config('aos.subject',%s,true)", (checker,))
        conn.execute("""SELECT public.ecommerce_d01_source_revoke_a0v_107(
            %s,%s,%s,%s,%s,%s)""",
            (proposal.selection_id,'c-revoke-'+suffix,'c'*64,checker,
             'decision withdrawn',revoked_at))
        conn.commit()
    with connect_serializable(scope) as conn:
        with pytest.raises(ValueError, match='approved D01 selection unavailable'):
            D01SourceSelectionStore().read_current(
                HostTransaction(conn), scope, run_id, plan_id, maker,
                conn.execute('SELECT clock_timestamp() AS now').fetchone()['now'])
