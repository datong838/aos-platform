import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from test_dispatch_successor_registration_pg import successor, register
from test_dispatch_first_registration_atomic_pg import (
    registered_db, receipt_db, database, connection, run,
)


pytestmark = pytest.mark.skipif(
    os.getenv('AOS_EXTENSION_PG_TEST') != '1', reason='dedicated PostgreSQL opt-in required')


def apply_upgrade(owner):
    path = Path(__file__).resolve().parents[2] / 'alembic/versions/a0v_073_uninstalled_successor_registration.py'
    spec = importlib.util.spec_from_file_location('a0v073_test', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = SimpleNamespace(execute=owner.execute)
    module.upgrade()


def add_uninstalled_head(case):
    owner = case.db.owner
    installation_pk = uuid4()
    source_id = case.request['installationRef']['installationId']
    source = owner.execute('''SELECT r.* FROM bundle_installation i
        JOIN bundle_installation_revision r USING(org_id,project_id,installation_pk)
        WHERE i.org_id='org-a' AND i.project_id='project-a' AND i.installation_id=%s
          AND r.revision=i.current_revision''', (source_id,)).fetchone()
    owner.execute('''INSERT INTO bundle_installation(org_id,project_id,installation_id,
        installation_pk,current_revision,active_revision,etag_version)
        VALUES('org-a','project-a',%s,%s,1,NULL,1)''',
        (case.old_install, installation_pk))
    owner.execute('''INSERT INTO bundle_installation_revision(org_id,project_id,installation_pk,
        revision,state,lock_hash,overlay_revision,composition_pk,lock_revision)
        VALUES('org-a','project-a',%s,1,'uninstalled',%s,%s,%s,%s)''',
        (installation_pk, source['lock_hash'], source['overlay_revision'],
         source['composition_pk'], source['lock_revision']))


def test_a0v073_preserves_disabled_predecessor(successor):
    apply_upgrade(successor.db.owner)
    assert register(successor)['executable'] is False


def test_a0v073_accepts_only_formally_uninstalled_stopped_predecessor(successor):
    owner = successor.db.owner
    apply_upgrade(owner)
    owner.execute("""UPDATE extension_runtime_binding
        SET desired_state='uninstalled',observed_state='stopped'
        WHERE installation_id=%s""", (successor.old_install,))
    with pytest.raises(Exception, match='predecessor must remain disabled'):
        register(successor)
    add_uninstalled_head(successor)
    assert register(successor)['executable'] is False
