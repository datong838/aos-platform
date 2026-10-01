"""Signed installation producer probe in a disposable full-schema PostgreSQL DB."""
import hashlib
import os
from contextlib import contextmanager

import pytest
from psycopg.conninfo import conninfo_to_dict

from aos_api.db import connect
from aos_api.extension_runtime.schema_registry import SchemaRequirement, apply_once
from aos_api.tenant_scope import TenantScope
from signed_installation_case import SCHEMA_PROBE_SQL, run_signed_installation
from tests.asset_registry import test_m2_core_integration as helper


pytestmark = [
    pytest.mark.skipif(os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='dedicated PG opt-in required'),
    pytest.mark.skipif(os.getenv('AOS_EXTENSION_OCI_TEST') != '1', reason='isolated OCI opt-in required'),
]
SCOPE = TenantScope('org-org', 'dev-project')


def test_signed_installation_producer_can_be_read_in_full_stage_schema(tmp_path):
    database = conninfo_to_dict(os.environ['AOS_DATABASE_URL'])['dbname']
    assert database.startswith('aos_test_') and database.endswith('_ti4_test')
    with connect(SCOPE) as conn:
        conn.execute("INSERT INTO meta_org(id,name) VALUES('org-org','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_workspace(org_id,project_id,name) VALUES('org-org','dev-project','isolated test') ON CONFLICT DO NOTHING")
        conn.execute("INSERT INTO meta_membership(org_id,project_id,subject,role) VALUES('org-org','dev-project','test-author','admin') ON CONFLICT DO NOTHING")

    def schema_setup(package_id):
        requirement = SchemaRequirement(
            package_id, '1', 'sha256:' + hashlib.sha256(SCHEMA_PROBE_SQL.encode()).hexdigest(),
        )
        # The isolated schema migration runs as the test database owner;
        # aos_runtime intentionally has no CREATE privilege on public.
        with connect() as conn:
            def migrate(scoped):
                scoped.execute(SCHEMA_PROBE_SQL)
            assert apply_once(conn, requirement, migrate) is True

    verified = []

    @contextmanager
    def worker_connect():
        with connect() as conn:
            conn.execute('SET ROLE aos_runtime')
            conn.commit()
            yield conn

    def verified_probe(*, connect, scope, installation, generation):
        assert scope == dict(org_id='org-org', project_id='dev-project')
        assert installation.state == 'active'
        with connect(SCOPE) as conn:
            conn.execute('SET LOCAL ROLE aos_runtime')
            row = conn.execute('''SELECT i.active_revision, b.generation, b.operation_fence,
                    b.enabled, b.observed_state
                FROM bundle_installation i JOIN extension_runtime_binding b
                  ON b.org_id=i.org_id AND b.project_id=i.project_id
                 AND b.installation_id=i.installation_id
                WHERE i.org_id=%s AND i.project_id=%s AND i.installation_id=%s''',
                (*SCOPE.key, installation.installation_id)).fetchone()
            assert row is not None
            assert row['active_revision'] == installation.active_revision
            assert row['generation'] == generation
            assert row['operation_fence'] is True and row['enabled'] is False
            assert row['observed_state'] == 'ready'
        verified.append(installation.installation_id)

    run_signed_installation(
        connect, helper, tmp_path, worker_mode='verify',
        schema_setup=schema_setup, verified_probe=verified_probe,
        worker_connect=worker_connect,
    )
    assert len(verified) == 1
