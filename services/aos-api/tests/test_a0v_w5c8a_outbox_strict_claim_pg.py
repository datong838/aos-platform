"""The Analysis-only strict claim must not recycle an ambiguous attempt."""

from contextlib import contextmanager

import psycopg
import pytest
from psycopg.rows import dict_row

from aos_api.data_requirement_outbox_store import DataRequirementOutboxStore
from aos_api.tenant_scope import TenantScope
from tests.aip._migration_test_support import isolated_aip_migration_database


SCOPE = TenantScope("org-org", "dev-project")
CANARY = TenantScope("dev-org", "dev-project")
TOPIC = "data.requirement.request"


def _seed(admin):
    for suffix in ("old", "pending", "unknown"):
        admin.execute(
            """INSERT INTO data_requirement_head
            (org_id,project_id,requirement_id,current_revision,current_content_hash,
             status,version,created_by)
            VALUES('org-org','dev-project',%s,1,%s,'accepted',1,'pytest')""",
            ("requirement-" + suffix, "a" * 64),
        )
        admin.execute(
            """INSERT INTO data_requirement_revision
            (org_id,project_id,requirement_id,revision,content_hash,status,operation,
             idempotency_key,request_hash,case_ref,run_ref,checkpoint_ref,payload,created_by)
            VALUES('org-org','dev-project',%s,1,%s,'accepted','request',
                   %s,%s,'{}','{}','{}','{}','pytest')""",
            ("requirement-" + suffix, "a" * 64, "seed-" + suffix, "b" * 64),
        )
        admin.execute(
            """INSERT INTO data_requirement_event
            (org_id,project_id,requirement_id,requirement_revision,event_id,sequence,
             event_type,to_status,payload,content_hash,created_by)
            VALUES('org-org','dev-project',%s,1,%s,1,'requested','accepted','{}',%s,'pytest')""",
            ("requirement-" + suffix, "event-" + suffix, "a" * 64),
        )
        admin.execute(
            """INSERT INTO data_requirement_outbox
            (org_id,project_id,outbox_id,requirement_id,requirement_revision,
             event_id,topic,payload,content_hash,created_by)
            VALUES('org-org','dev-project',%s,%s,1,%s,%s,'{}',%s,'pytest')""",
            ("outbox-" + suffix, "requirement-" + suffix,
             "event-" + suffix, TOPIC, "a" * 64),
        )
    admin.commit()


def test_strict_pending_claim_freezes_expired_and_unknown_without_cross_tenant_read():
    with isolated_aip_migration_database(
        "w5c8a_strict_claim", migration_target="a0v_095"
    ) as (_config, dsn):
        with psycopg.connect(dsn) as admin:
            _seed(admin)

        @contextmanager
        def runtime_connect(scope):
            with psycopg.connect(dsn, row_factory=dict_row) as conn:
                conn.execute("SET LOCAL ROLE aos_runtime")
                conn.execute(
                    "SELECT set_config('aos.org_id',%s,true),"
                    "set_config('aos.project_id',%s,true)", scope.key,
                )
                yield conn

        store = DataRequirementOutboxStore(runtime_connect)
        old = store.claim_next(
            SCOPE, topic=TOPIC, worker_id="old-worker", lease_token="old-token",
            lease_seconds=300,
        )
        assert old and old.outbox_id == "outbox-old" and old.attempt == 1
        unknown = store.claim_next(
            SCOPE, topic=TOPIC, worker_id="unknown-worker",
            lease_token="unknown-token", lease_seconds=300,
        )
        assert unknown and unknown.outbox_id == "outbox-pending"
        assert store.mark_unknown(
            SCOPE, unknown.outbox_id, unknown.lease_token,
            reason_code="COMMIT_RESULT_UNKNOWN",
        ).state == "unknown"
        with psycopg.connect(dsn) as admin:
            admin.execute(
                """UPDATE data_requirement_outbox_delivery
                   SET lease_expires_at=NOW()-INTERVAL '1 second'
                 WHERE org_id='org-org' AND project_id='dev-project'
                   AND outbox_id='outbox-old'"""
            )
            admin.commit()

        ambiguous = store.read_ambiguous_next(SCOPE, topic=TOPIC)
        assert ambiguous and ambiguous.outbox_id == "outbox-old"
        assert store.read_ambiguous_next(CANARY, topic=TOPIC) is None
        pending = store.claim_pending_next(
            SCOPE, topic=TOPIC, worker_id="new-worker", lease_token="new-token",
            lease_seconds=300,
        )
        assert pending and pending.outbox_id == "outbox-unknown" and pending.attempt == 1
        assert store.claim_pending_next(
            SCOPE, topic=TOPIC, worker_id="no-reclaim", lease_token="no-reclaim-token",
            lease_seconds=300,
        ) is None
        with psycopg.connect(dsn, row_factory=dict_row) as admin:
            rows = admin.execute(
                """SELECT outbox_id,state,attempt FROM data_requirement_outbox_delivery
                   WHERE org_id='org-org' AND project_id='dev-project'
                   ORDER BY outbox_id"""
            ).fetchall()
        assert [(r["outbox_id"], r["state"], r["attempt"]) for r in rows] == [
            ("outbox-old", "claimed", 1),
            ("outbox-pending", "unknown", 1),
            ("outbox-unknown", "claimed", 1),
        ]


def test_strict_pending_function_denies_direct_runtime_delivery_write():
    with isolated_aip_migration_database(
        "w5c8a_strict_acl", migration_target="a0v_095"
    ) as (_config, dsn):
        with psycopg.connect(dsn) as admin:
            _seed(admin)
        with psycopg.connect(dsn) as conn:
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','org-org',true),"
                "set_config('aos.project_id','dev-project',true)"
            )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(
                    """UPDATE data_requirement_outbox_delivery SET state='acked'
                       WHERE org_id='org-org' AND project_id='dev-project'"""
                )
