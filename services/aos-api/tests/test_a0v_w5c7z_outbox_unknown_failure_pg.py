"""No-effect PG reproduction of an unpersisted Outbox unknown marker."""

from contextlib import contextmanager

import psycopg
import pytest
from psycopg.rows import dict_row

from aos_api.data_requirement_outbox_store import (
    DataRequirementOutboxConflict,
    DataRequirementOutboxStore,
)
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


SCOPE = TenantScope(org_id="org-org", project_id="dev-project")
CANARY = TenantScope(org_id="dev-org", project_id="dev-project")
TOPIC = "data.requirement.request"


def test_failed_unknown_marker_leaves_expired_claim_reclaimable_without_source_call():
    with isolated_aip_migration_database(
        "w5c7z_outbox_unknown", migration_target="biw2_004"
    ) as (_config, dsn):
        with psycopg.connect(dsn) as admin:
            admin.execute(
                """INSERT INTO data_requirement_head
                (org_id,project_id,requirement_id,current_revision,current_content_hash,
                 status,version,created_by)
                VALUES('org-org','dev-project','requirement-1',1,%s,'accepted',1,'pytest')""",
                ("a" * 64,),
            )
            admin.execute(
                """INSERT INTO data_requirement_revision
                (org_id,project_id,requirement_id,revision,content_hash,status,operation,
                 idempotency_key,request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by)
                VALUES('org-org','dev-project','requirement-1',1,%s,'accepted','request',
                       'seed',%s,'{}','{}','{}','{}','pytest')""",
                ("a" * 64, "b" * 64),
            )
            admin.execute(
                """INSERT INTO data_requirement_event
                (org_id,project_id,requirement_id,requirement_revision,event_id,sequence,
                 event_type,to_status,payload,content_hash,created_by)
                VALUES('org-org','dev-project','requirement-1',1,'event-1',1,
                       'requested','accepted','{}',%s,'pytest')""",
                ("a" * 64,),
            )
            admin.execute(
                """INSERT INTO data_requirement_outbox
                (org_id,project_id,outbox_id,requirement_id,requirement_revision,
                 event_id,topic,payload,content_hash,created_by)
                VALUES('org-org','dev-project','outbox-1','requirement-1',1,
                       'event-1',%s,'{}',%s,'pytest')""",
                (TOPIC, "a" * 64),
            )
            admin.commit()

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),"
                    "set_config('aos.project_id',%s,true)",
                    scope.key,
                )
                yield conn

        store = DataRequirementOutboxStore(runtime_connect)
        first = store.claim_next(
            SCOPE, topic=TOPIC, worker_id="worker-1", lease_token="token-1",
            lease_seconds=300,
        )
        assert first is not None and first.attempt == 1
        assert store.claim_next(
            CANARY, topic=TOPIC, worker_id="canary", lease_token="canary-token",
            lease_seconds=300,
        ) is None

        # This deterministic SQL rejection represents a marker that did not persist;
        # no coordinator or source reader is invoked by the test.
        with pytest.raises(DataRequirementOutboxConflict):
            store.mark_unknown(
                SCOPE, "outbox-1", "wrong-token", reason_code="COMMIT_RESULT_UNKNOWN"
            )
        with psycopg.connect(dsn, row_factory=dict_row) as admin:
            row = admin.execute(
                """SELECT state,attempt,lease_token FROM data_requirement_outbox_delivery
                WHERE org_id='org-org' AND project_id='dev-project'
                  AND outbox_id='outbox-1'"""
            ).fetchone()
            assert row == {"state": "claimed", "attempt": 1, "lease_token": "token-1"}
            admin.execute(
                """UPDATE data_requirement_outbox_delivery
                SET lease_expires_at=NOW()-INTERVAL '1 second'
                WHERE org_id='org-org' AND project_id='dev-project'
                  AND outbox_id='outbox-1'"""
            )
            admin.commit()

        second = store.claim_next(
            SCOPE, topic=TOPIC, worker_id="worker-2", lease_token="token-2",
            lease_seconds=300,
        )
        assert second is not None
        assert (second.outbox_id, second.attempt, second.lease_token) == (
            first.outbox_id, 2, "token-2"
        )

        # A committed ACK stays unclaimable even if the caller loses its response.
        acked = store.ack(SCOPE, second.outbox_id, second.lease_token)
        assert acked.state == "acked"
        assert store.claim_next(
            SCOPE, topic=TOPIC, worker_id="worker-3", lease_token="token-3",
            lease_seconds=300,
        ) is None
