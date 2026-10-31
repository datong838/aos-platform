"""Durable four-policy renewal session; actual wiring is added separately."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from typing import Callable, Mapping, Optional

BASE = Path(__file__).resolve().parent
ROOT = BASE.parents[1]
sys.path[:0] = [
    str(BASE),
    str(ROOT / "services/aos-api"),
    str(ROOT / "services/aos-api/tests/extension_runtime"),
]

import psycopg
from psycopg.rows import dict_row

from aos_api import db
from aos_api.aip_budget_store import (
    AipBudgetAuthorityStore,
    canonical_hash,
    materialize_revision,
)
from aos_api.aip_model_governance_policy_store import (
    AipModelGovernancePolicyStore,
    materialize_policy as quota_materialize,
)
from aos_api.aip_runtime_guard_policy_store import (
    AipRuntimeGuardPolicyStore,
    materialize_policy as guard_materialize,
)
from aos_api.asset_registry.canonical_json import canonical_sha256
from aos_api.tenant_scope import TenantScope, apply_transaction_scope
from aos_api.extension_runtime.oci_driver import OciDriver
import selected_three_backend_case as selected
import test_selected_three_backend_lifecycle_pg as original
from test_selected_three_backend_lifecycle_pg import build_initial_policy_drafts
from t2_durable_activation_intent_r409 import DurableActivationJournal
from t2_original_connection_r569 import IDENTITY_SQL, validate_identity
from t2_policy_draft_renewal_r883 import (
    STEPS,
    build_policy_draft_renewals,
    build_renewal_descriptors,
)


AUTHORITY = "AOS-002055"
HEAD = "deeba368a35ac3cda289d7bc07794c5a91fa8d00"
SOURCE_TASK = "qyh-m2-three-backend-runner-20261023-h1027-h1029-h1031"
ACTUAL_TASK = "qyh-m2-native166-original-history-actual-20261027-h1029-h1031"
WRITER = "codex-01a190f8-e1f7-7631-821c-3ac7b969bc40"
SCOPE = {"orgId": "org-org", "projectId": "dev-project"}
EFFECTIVE_FROM = datetime(2026, 10, 31, 14, 50, tzinfo=UTC)
ORIGINAL_CLOCK = datetime(2026, 10, 28, 6, 40, 41, 433192, tzinfo=UTC)
RECEIPT_PATTERN = re.compile(r"aip10[rgp]-[0-9a-f]{20}")
TENANT_SCOPE = TenantScope("org-org", "dev-project")
ACTOR = "synthetic-m2-three-t2-source-author"
SPECS = {
    "budget": {
        "table": "aip_budget_receipt",
        "prefix": "aip10r-",
        "materialize": materialize_revision,
        "resourceType": "BudgetRevision",
    },
    "egress": {
        "table": "aip_runtime_guard_policy_receipt",
        "prefix": "aip10g-",
        "materialize": guard_materialize,
        "resourceType": "EgressPolicyRevision",
    },
    "data": {
        "table": "aip_runtime_guard_policy_receipt",
        "prefix": "aip10g-",
        "materialize": guard_materialize,
        "resourceType": "DataClassificationPolicyRevision",
    },
    "quota": {
        "table": "aip_model_governance_policy_receipt",
        "prefix": "aip10p-",
        "materialize": quota_materialize,
        "resourceType": "QuotaPolicyRevision",
    },
}
PROJECT_ROOT = ROOT.parent
CONTEXT = PROJECT_ROOT / "docs/palantier/AOS项目开发上下文"
ACTUAL_DIR = ROOT / ".evidence/qyh-m2-native166-original-history-actual-20261027"
DSN = (
    "host=127.0.0.1 port=18458 dbname=aos_refresh_activation_native "
    "user=aos_refresh_activation_native_migrator connect_timeout=5 "
    "application_name=t2-policy-renewal-r884"
)
CONNECTION_TASK = "qyh-m2-policy-renewal-connection-20261031"
TASKS = (SOURCE_TASK, ACTUAL_TASK, CONNECTION_TASK)
CONTAINER_ID = "8ad56b817e7c81db6ebf57ddfd4d064bb583ba79f80fbec4a9e78164eec5095f"
CONTAINER_IMAGE = "sha256:7e7dbab8d3b431a20793a6d99cb5a6bc84e44914309917f1bf5589a7568cdefd"
EXPECTED_CLUSTER = "qyh-canonical166-8af8248e67b4128101100eda"
PROTECTED_DIRTY = ROOT / ".evidence/qyh-cost-model-route-renewal-20261031/human-native-cost-playbook.md"


def original_requests():
    """Rebuild the exact revision-1 drafts without reading or writing a database."""
    return build_initial_policy_drafts("m2-three-t2", ORIGINAL_CLOCK).requests


def renewal_requests():
    return build_policy_draft_renewals(original_requests(), effective_from=EFFECTIVE_FROM)


def renewal_descriptors():
    return build_renewal_descriptors(renewal_requests())


def expected_journal_identity():
    return {
        "authority": AUTHORITY,
        "head": HEAD,
        "sourceTask": SOURCE_TASK,
        "actualTask": ACTUAL_TASK,
        "writer": WRITER,
        "scope": dict(SCOPE),
        "effectiveFrom": EFFECTIVE_FROM.isoformat().replace("+00:00", "Z"),
        "authorizedUntil": "2027-03-31T04:00:00Z",
    }


def _validate_identity(value):
    expected = expected_journal_identity()
    if type(value) is not dict or value != expected:
        raise ValueError("renewal identity differs")
    result = dict(value)
    result["scope"] = dict(value["scope"])
    return result


def _validate_operation_id(value, name):
    if type(value) is not str or RECEIPT_PATTERN.fullmatch(value) is None:
        raise ValueError(f"{name} must be an exact policy Receipt id")
    return value


class RenewalJournal(DurableActivationJournal):
    """Specialize the existing append-only journal for the four draft renewals."""

    SCHEMA = "aos-t2-policy-draft-renewal-journal/v1"
    STEPS = STEPS
    validate_identity = staticmethod(_validate_identity)
    validate_operation_id = staticmethod(_validate_operation_id)

    def _validate_descriptor(self, step, value):
        expected = dict(renewal_descriptors()[self.STEPS.index(step)])
        if type(value) is not dict or value != expected:
            raise ValueError("renewal descriptor differs")
        return dict(value)


def _get_revision(step, connect, conn, request):
    resource_id = renewal_descriptors()[STEPS.index(step)]["resourceId"]
    if step == "budget":
        return AipBudgetAuthorityStore(connect).get(
            TENANT_SCOPE, resource_id, 2, conn=conn
        )
    if step == "quota":
        return AipModelGovernancePolicyStore(connect)._get(
            "quota", TENANT_SCOPE, resource_id, 2, conn=conn
        )
    return AipRuntimeGuardPolicyStore(connect)._get(
        "egress" if step == "egress" else "data_classification",
        TENANT_SCOPE,
        resource_id,
        2,
        conn=conn,
    )


class RenewalReceiptReader:
    """Read the exact immutable Receipt and revision-2 draft in one RO scope."""

    def __init__(self, *, connect):
        if not callable(connect):
            raise TypeError("readonly connection factory required")
        self.connect = connect
        self.requests = renewal_requests()
        self.descriptors = renewal_descriptors()

    def read(self, step):
        if step not in STEPS:
            raise ValueError("fixed renewal step required")
        index = STEPS.index(step)
        descriptor = self.descriptors[index]
        request = self.requests[index]
        spec = SPECS[step]
        try:
            with self.connect() as conn:
                apply_transaction_scope(conn, TENANT_SCOPE)
                validate_identity(dict(conn.execute(IDENTITY_SQL).fetchone()), scoped=True)
                row = conn.execute(
                    "SELECT receipt_id,request_hash,result_ref,created_by FROM "
                    + spec["table"]
                    + " WHERE org_id=%s AND project_id=%s AND operation=%s "
                    "AND idempotency_key=%s",
                    (*TENANT_SCOPE.key, descriptor["operation"], descriptor["idempotencyKey"]),
                ).fetchone()
                if row is None:
                    return None
                if (
                    set(row) != {"receipt_id", "request_hash", "result_ref", "created_by"}
                    or row["request_hash"] != descriptor["requestHash"]
                    or row["created_by"] != ACTOR
                    or type(row["receipt_id"]) is not str
                    or not row["receipt_id"].startswith(spec["prefix"])
                ):
                    raise ValueError("renewal Receipt differs")
                _validate_operation_id(row["receipt_id"], "receipt_id")
                fact = _get_revision(step, self.connect, conn, request)
                expected = spec["materialize"](
                    TENANT_SCOPE, ACTOR, request, created_at=fact.created_at
                )
                if (
                    type(fact) is not type(expected)
                    or fact.model_dump(mode="json", by_alias=True)
                    != expected.model_dump(mode="json", by_alias=True)
                ):
                    raise ValueError("renewal revision differs from frozen request")
                result_ref = {
                    "resourceType": spec["resourceType"],
                    "resourceId": descriptor["resourceId"],
                    "revision": 2,
                    "contentHash": fact.content_hash,
                }
                if canonical_hash(row["result_ref"]) != canonical_hash(result_ref):
                    raise ValueError("renewal Receipt reference differs")
                validate_identity(dict(conn.execute(IDENTITY_SQL).fetchone()), scoped=True)
                return {
                    "operationId": row["receipt_id"],
                    "factHash": canonical_sha256(
                        {
                            "receipt": dict(row),
                            "revision": fact.model_dump(mode="json", by_alias=True),
                        }
                    ),
                }
        except psycopg.Error:
            raise RuntimeError(
                "renewal readback unavailable; never republish an unknown attempt"
            ) from None


class StorePublisher:
    """Narrow original Store adapter; no policy activation methods are exposed."""

    def __init__(self, *, connect):
        if not callable(connect):
            raise TypeError("policy Store connection factory required")
        self.connect = connect

    def __call__(self, step, request, descriptor):
        if descriptor != renewal_descriptors()[STEPS.index(step)]:
            raise ValueError("renewal descriptor differs")
        if step == "budget":
            publish = AipBudgetAuthorityStore(self.connect).publish
        elif step == "egress":
            publish = AipRuntimeGuardPolicyStore(self.connect).publish_egress
        elif step == "data":
            publish = AipRuntimeGuardPolicyStore(self.connect).publish_data_classification
        elif step == "quota":
            publish = AipModelGovernancePolicyStore(self.connect).publish_quota
        else:
            raise ValueError("fixed renewal step required")
        returned = publish(
            TENANT_SCOPE,
            ACTOR,
            descriptor["idempotencyKey"],
            request,
            expected_version=1,
        )
        expected = SPECS[step]["materialize"](
            TENANT_SCOPE, ACTOR, request, created_at=returned.created_at
        )
        if (
            type(returned) is not type(expected)
            or returned.model_dump(mode="json", by_alias=True)
            != expected.model_dump(mode="json", by_alias=True)
        ):
            raise ValueError("renewal publish returned unexpected revision")
        return returned


class RenewalSession:
    """Issue at most one new mutation and reconcile every attempted mutation first."""

    def __init__(self, *, journal: RenewalJournal, reader, publish: Callable,
                 admit_current: Callable[[], None]):
        self.journal = journal
        self.reader = reader
        self.publish = publish
        self.admit_current = admit_current
        self.identity = expected_journal_identity()
        self.requests = renewal_requests()
        self.descriptors = renewal_descriptors()

    def _readback(self, step):
        value = self.reader.read(step)
        if value is None:
            raise LookupError(f"{step} outcome unknown; readonly reconciliation only")
        return value

    def recover(self):
        readbacks = {}
        while True:
            state = self.journal.recover(self.identity, readbacks=readbacks)
            if state.mode == "ISSUE" or state.mode == "COMPLETE":
                return state
            value = self._readback(state.step)
            if state.mode == "OBSERVE":
                readbacks[state.step] = value
                continue
            if state.mode != "RECONCILE":
                raise ValueError("renewal recovery mode differs")
            self.journal.freeze_settled(
                state.step,
                operation_id=value["operationId"],
                fact_hash=value["factHash"],
            )
            readbacks[state.step] = value

    def issue_one(self):
        state = self.recover()
        if state.mode == "COMPLETE":
            raise FileExistsError("renewal already complete")
        if state.mode != "ISSUE":
            raise ValueError("renewal is not issuable")
        index = self.journal.STEPS.index(state.step)
        if self.reader.read(state.step) is not None:
            raise FileExistsError(
                "pre-existing renewal Receipt requires separate readonly reconciliation"
            )
        self.admit_current()
        self.journal.freeze_attempt(state.step, self.descriptors[index])
        try:
            self.publish(state.step, self.requests[index], self.descriptors[index])
        except Exception as exc:
            raise RuntimeError(
                f"{state.step} outcome unknown; readonly reconciliation only"
            ) from exc
        return self.recover()


def create_journal(root: Path):
    return RenewalJournal.create(root, expected_journal_identity())


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _command(arguments):
    return subprocess.run(
        arguments, cwd=ROOT, check=True, text=True, capture_output=True
    ).stdout.strip()


def expected_environment():
    return {
        "AOS_DATABASE_URL": DSN,
        "AOS_TWA_STORE": "pg",
        "PGOPTIONS": "-c default_transaction_read_only=off",
        "PGPASSFILE": "/dev/null",
    }


def _validate_environment():
    expected = expected_environment()
    if any(os.environ.get(key) != value for key, value in expected.items()):
        raise ValueError("exact isolated renewal environment required")
    if any(key.startswith("PG") and key not in expected for key in os.environ):
        raise ValueError("inherited PG environment refused")


def _validate_raw_identity(row, *, scoped, readonly):
    expected = {
        "database": "aos_refresh_activation_native",
        "oid": 16384,
        "cluster": EXPECTED_CLUSTER,
        "version": 160014,
        "session": "aos_refresh_activation_native_migrator",
        "role": "aos_runtime" if scoped else "aos_refresh_activation_native_migrator",
        "readonly": "on" if readonly else "off",
        "superuser": False,
        "inherit": False,
        "bypassrls": False,
        "createdb": False,
        "createrole": False,
        "replication": False,
        "org": "org-org" if scoped else None,
        "project": "dev-project" if scoped else None,
    }
    if row != expected or any(type(row[key]) is not type(value) for key, value in expected.items()):
        raise ValueError("isolated renewal connection identity differs")


def admit(intent):
    required = {
        "schema", "authority", "head", "owner", "thread", "sourceFiles",
        "taskHashes", "ssh", "protectedDirtyHash", "containerId", "containerImage",
    }
    if (
        type(intent) is not dict
        or set(intent) != required
        or intent["schema"] != "aos-t2-policy-draft-renewal-actual/v1"
        or intent["authority"] != AUTHORITY
        or intent["head"] != HEAD
        or intent["owner"] != WRITER
        or intent["thread"] != "01a190f8-e1f7-7631-821c-3ac7b969bc40"
        or set(intent["taskHashes"]) != set(TASKS)
        or intent["containerId"] != CONTAINER_ID
        or intent["containerImage"] != CONTAINER_IMAGE
    ):
        raise ValueError("exact renewal execution intent required")
    _validate_environment()
    handoff = _read(CONTEXT / "交接/latest-handoff.json")
    if (
        handoff.get("phase") != "CUTOVER_COMPLETE"
        or handoff.get("currentThreadId") != intent["thread"]
        or _read(handoff["transaction"]).get("phase") != "CUTOVER_COMPLETE"
    ):
        raise ValueError("current handoff differs")
    if (
        _command(["git", "branch", "--show-current"]) != "m1"
        or _command(["git", "rev-parse", "HEAD"]) != HEAD
        or _command(["git", "diff", "--cached", "--name-only"])
        or _sha(PROTECTED_DIRTY) != intent["protectedDirtyHash"]
    ):
        raise ValueError("m1 HEAD, index, or protected Cursor change differs")
    for name, digest in intent["sourceFiles"].items():
        if _sha(ROOT / name) != digest:
            raise ValueError("renewal source pin differs")
    leases = _read(CONTEXT / "memory/leases.json")["leases"]
    now = datetime.now(UTC)
    for task_id, digest in intent["taskHashes"].items():
        path = CONTEXT / f"memory/receipts/tasks/{task_id}.json"
        task = _read(path)
        matches = [item for item in leases if item.get("task_id") == task_id]
        if (
            _sha(path) != digest
            or task.get("status") != "ACTIVE"
            or task.get("owner") != WRITER
            or task.get("base_revision") != AUTHORITY
            or matches != [task]
            or datetime.fromisoformat(task["lease_expires_at"]).astimezone(UTC) <= now
        ):
            raise ValueError("current renewal Task or Lease differs")
    ssh = intent["ssh"]
    if type(ssh) is not dict or set(ssh) != {"pid", "start"} or type(ssh["pid"]) is not int:
        raise ValueError("exact renewal SSH fingerprint required")
    process = _command(["ps", "-o", "lstart=,command=", "-p", str(ssh["pid"])])
    listener = _command(["lsof", "-nP", f"-a", f"-p{ssh['pid']}", "-iTCP:18458", "-sTCP:LISTEN"])
    if ssh["start"] not in process or "127.0.0.1:18458" not in listener:
        raise ValueError("renewal SSH process differs")
    inspected = _command([
        "docker", "--context", "colima-aos-extension", "inspect", CONTAINER_ID,
        "--format", "{{.Id}}|{{.State.Status}}|{{.Config.Image}}|{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}",
    ])
    if inspected != f"{CONTAINER_ID}|running|{CONTAINER_IMAGE}|172.24.0.2":
        raise ValueError("canonical isolated PostgreSQL container differs")


def composition(intent, *, readonly):
    @contextmanager
    def writer():
        if readonly:
            raise PermissionError("readonly reconciliation cannot open writer")
        admit(intent)
        with psycopg.connect(DSN, row_factory=dict_row) as conn:
            conn.execute("SET client_encoding TO 'UTF8'")
            _validate_raw_identity(dict(conn.execute(IDENTITY_SQL).fetchone()), scoped=False, readonly=False)
            conn.rollback()
            yield conn
            _validate_raw_identity(dict(conn.execute(IDENTITY_SQL).fetchone()), scoped=True, readonly=False)

    @contextmanager
    def reader():
        admit(intent)
        with db.connect_read_only(scope=TENANT_SCOPE, inherit_scope=False) as conn:
            _validate_raw_identity(dict(conn.execute(IDENTITY_SQL).fetchone()), scoped=True, readonly=True)
            yield conn

    def refused():
        raise PermissionError("renewal wave has no maintenance, command, or runtime authority")

    identity = selected.SelectedLabIdentity(
        "aos_refresh_activation_native", 16384, EXPECTED_CLUSTER, "aos_app"
    )
    lab = original.SelectedLifecycleLab(
        runtime_connect=writer,
        maintenance_connect=refused,
        command_connect=refused,
        driver=OciDriver(context="colima-aos-extension"),
        identity=identity,
    )
    return lab, reader


def _reserve(path):
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    return os.fdopen(descriptor, "w", encoding="utf-8")


def _finish(handle, value):
    json.dump(value, handle, ensure_ascii=False, sort_keys=True, indent=2)
    handle.write("\n")
    handle.flush()
    os.fsync(handle.fileno())


def run(*, intent_path, journal_path, result_path, readonly=False):
    with _reserve(result_path) as handle:
        outcomes = []
        try:
            intent = _read(intent_path)
            admit(intent)
            lab, reader_connect = composition(intent, readonly=readonly)
            journal = RenewalJournal.open(journal_path) if readonly else create_journal(journal_path)
            reader = RenewalReceiptReader(connect=reader_connect)
            session = RenewalSession(
                journal=journal,
                reader=reader,
                publish=StorePublisher(connect=lab.policy_store_connect),
                admit_current=lambda: admit(intent),
            )
            if readonly:
                outcomes.append(session.recover().mode)
            else:
                for _ in STEPS:
                    outcomes.append(session.issue_one().mode)
                if outcomes != ["ISSUE", "ISSUE", "ISSUE", "COMPLETE"]:
                    raise ValueError("four renewal draft sequence incomplete")
            facts = {step: reader.read(step) for step in STEPS}
            _finish(handle, {
                "schema": "aos-t2-policy-draft-renewal-result/v1",
                "at": datetime.now(UTC).isoformat(),
                "mode": "readonly" if readonly else "fresh",
                "outcomes": outcomes,
                "facts": facts,
                "unknown": False,
                "activePoliciesCreated": False,
                "providerCalled": False,
            })
        except Exception as exc:
            _finish(handle, {
                "schema": "aos-t2-policy-draft-renewal-result/v1",
                "outcomes": outcomes,
                "status": "STOPPED_READONLY_RECONCILE",
                "errorType": type(exc).__name__,
                "unknown": True,
            })
            raise RuntimeError(
                "renewal driver stopped; preserve journal and use readonly reconciliation"
            ) from None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--intent", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--readonly", action="store_true")
    args = parser.parse_args()
    run(
        intent_path=args.intent,
        journal_path=args.journal,
        result_path=args.result,
        readonly=args.readonly,
    )


if __name__ == "__main__":
    main()
