"""Native r6c/r6d transaction matrix on an explicit disposable PostgreSQL clone.

This module has no shared-database fallback.  The matrix remains skipped until
an operator supplies a loopback test template through the dedicated variable.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import timedelta
import hashlib
import json
import os
import secrets
from types import SimpleNamespace
from typing import Any
from uuid import UUID
from uuid import uuid4
from uuid import uuid5, NAMESPACE_URL

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
import pytest

import aos_api.aip_model_route_eval_atomic_finalizer as finalizer
from aos_api.aip_budget_reservation_contracts import (
    BudgetExactRef, BudgetReservationState, exact_ref_payload,
)
from aos_api.aip_budget_reservation_store import AipBudgetReservationStore, canonical_hash
from aos_api.aip_eval_contracts import EvalRunAuthorityRecord
from aos_api.aip_model_route_eval_execution_journal import _canonical
from aos_api.aip_model_route_eval_finalization_proof import (
    RouteEvalFinalizationProofStore,
)
from aos_api.aip_model_route_eval_finalization_reconcile import (
    reconcile_route_eval_finalization,
)
from aos_api.aip_model_route_eval_report_proof_reader import (
    read_verified_route_eval_report_from_persistence,
)
from aos_api.aip_model_route_eval_signatures import _manifest
from aos_api.aip_telemetry_usage_service import AipTelemetryUsageService
from aos_api.tenant_scope import TenantScope
from test_model_route_eval_atomic_finalizer import fixture as finalization_fixture


ENV = "AOS_ROUTE_EVAL_NATIVE_TEST_ADMIN_URL"
DATABASE_PREFIX = "aos_test_"
DATABASE_SUFFIX = "_ti4_test"
LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
SOURCE_TABLES = (
    "aip_route_eval_execution_command",
    "aip_route_eval_execution_result",
    "aip_route_eval_finalization_proof",
    "aip_route_eval_release_material",
    "aip_route_eval_finalized_call_proof",
)
SCOPE = TenantScope("org-org", "dev-project")


@dataclass(frozen=True)
class NativeCase:
    proof: Any
    manifest: bytes
    presented: tuple[Any, ...]
    report: Any
    event: Any
    expected_run_version: int
    run: EvalRunAuthorityRecord
    journal: dict[UUID, dict[str, Any]]
    usage_rows: dict[UUID, tuple[dict[str, Any], ...]]


class NativeMatrixConfigurationError(RuntimeError):
    """The supplied URL could touch a non-disposable database."""


def _validated_admin_dsn(raw: str | None) -> tuple[str, dict[str, str]]:
    if not raw:
        pytest.skip(f"explicit disposable PostgreSQL template required via {ENV}")
    try:
        parts = conninfo_to_dict(raw)
        host = parts.get("host")
        port = int(parts.get("port", "0"))
        database = parts.get("dbname", "")
        if (
            host not in LOOPBACK_HOSTS
            or port < 1024
            or port == 5432
            or not database.startswith(DATABASE_PREFIX)
            or not database.endswith(DATABASE_SUFFIX)
            or not parts.get("user")
            or not parts.get("password")
            or parts.get("require_auth") != "scram-sha-256"
        ):
            raise ValueError
    except (TypeError, ValueError):
        raise NativeMatrixConfigurationError(
            "route finalization native tests require a loopback, non-default-port "
            "aos_test_*_ti4_test template with require_auth=scram-sha-256"
        ) from None
    return raw, parts


def _source_counts(conn: psycopg.Connection) -> tuple[int, ...]:
    return tuple(
        conn.execute(sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(table))).fetchone()[0]
        for table in SOURCE_TABLES
    )


@contextmanager
def _disposable_clone(raw: str):
    source_dsn, parts = _validated_admin_dsn(raw)
    source_database = parts["dbname"]
    clone_database = f"{DATABASE_PREFIX}{uuid4().hex[:12]}{DATABASE_SUFFIX}"
    login = f"route_finalizer_test_{uuid4().hex[:12]}"
    password = secrets.token_urlsafe(32)
    clone_created = role_created = False
    source_before: tuple[int, ...] | None = None
    try:
        with psycopg.connect(source_dsn, autocommit=True) as admin:
            source_before = _source_counts(admin)
            required = set(SOURCE_TABLES) | {
                "aip_eval_run", "aip_eval_run_event", "aip_eval_report_revision",
                "aip_lineage_event", "aip_usage_receipt", "aip_budget_reservation",
            }
            present = {
                row[0] for row in admin.execute(
                    "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname='public'"
                ).fetchall()
            }
            if not required.issubset(present):
                raise NativeMatrixConfigurationError(
                    "disposable template is not migrated through the r6c/r6d schema"
                )
            admin.execute(sql.SQL(
                "CREATE ROLE {} LOGIN NOINHERIT NOSUPERUSER NOBYPASSRLS "
                "NOCREATEROLE NOCREATEDB NOREPLICATION PASSWORD {}"
            ).format(sql.Identifier(login), sql.Literal(password)))
            role_created = True
            admin.execute(sql.SQL("GRANT aos_runtime,aos_route_eval_finalizer TO {}").format(
                sql.Identifier(login)))
            admin.execute(sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(clone_database), sql.Identifier(source_database)))
            clone_created = True
        clone_dsn = make_conninfo(
            **{**parts, "dbname": clone_database, "user": login, "password": password}
        )
        clone_admin_dsn = make_conninfo(**{**parts, "dbname": clone_database})
        yield clone_dsn, clone_admin_dsn, clone_database, login, source_before
    finally:
        if clone_created or role_created:
            with psycopg.connect(source_dsn, autocommit=True) as admin:
                if clone_created:
                    admin.execute(
                        "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                        "WHERE datname=%s AND pid<>pg_backend_pid()",
                        (clone_database,),
                    )
                    admin.execute(sql.SQL("DROP DATABASE IF EXISTS {}").format(
                        sql.Identifier(clone_database)))
                if role_created:
                    admin.execute(sql.SQL("REVOKE aos_runtime,aos_route_eval_finalizer FROM {}").format(
                        sql.Identifier(login)))
                    admin.execute(sql.SQL("DROP ROLE IF EXISTS {}").format(sql.Identifier(login)))
                if source_before is not None and _source_counts(admin) != source_before:
                    raise AssertionError("native matrix modified its source template")


@pytest.fixture()
def native_clone():
    with _disposable_clone(os.getenv(ENV)) as value:
        yield value


def _dump(value: Any) -> dict[str, Any] | None:
    if value is None:
        return None
    return value.model_dump(mode="json", by_alias=True)


def _optional_jsonb(value: Any):
    payload = _dump(value)
    return None if payload is None else Jsonb(payload)


def _prepare_native_case(*, real_services: bool = False) -> NativeCase:
    proof, manifest, presented, journal, report, event, version = finalization_fixture()
    run = EvalRunAuthorityRecord.model_validate(_manifest(manifest)["context"]["run"])
    updated_calls = []
    persisted: dict[UUID, dict[str, Any]] = {}
    usage_rows: dict[UUID, tuple[dict[str, Any], ...]] = {}
    for item in proof.calls:
        evidence = journal.items[item.reservation_id]
        request = evidence["command"].budget_request
        invocation_id = item.reservation_id
        invocation_ref, reservation_ref = AipBudgetReservationStore.initial_hold_refs(
            request, invocation_id=invocation_id, reservation_id=item.reservation_id
        )
        command = evidence["command"].model_copy(update={
            "invocation_ref": invocation_ref,
            "reservation_ref": reservation_ref,
        })
        result = evidence["result"]
        if real_services:
            request_receipt_id = uuid5(
                NAMESPACE_URL, f"aos-route-eval:{item.reservation_id}"
            )
            provider_ref = BudgetExactRef(
                resourceType="ProviderInstanceRevision",
                resourceId=result.provider_id,
                revision=1,
                contentHash="sha256:" + "d" * 64,
            )
            provider_idempotency_hash = hashlib.sha256(
                f"route-eval:{item.call_key}".encode()
            ).hexdigest()
            request_payload = {
                "invocationId": str(invocation_id),
                "requestHash": request.request_hash(),
                "providerRef": exact_ref_payload(provider_ref),
                "providerIdempotencyHash": provider_idempotency_hash,
            }
            request_ref = BudgetExactRef(
                resourceType="CapabilityProviderRequestReceipt",
                resourceId=str(request_receipt_id),
                revision=1,
                contentHash=canonical_hash(request_payload, prefixed=True),
            )
            result = result.model_copy(update={"provider_request_ref": request_ref})
        _, command_hash = _canonical(command)
        _, result_hash = _canonical(result)
        rows = []
        refs = []
        for index, (kind, quantity, old_ref) in enumerate(zip(
            ("input_token", "output_token"),
            (result.prompt_tokens, result.completion_tokens),
            item.usage_receipt_refs,
            strict=True,
        )):
            receipt_id = (
                AipTelemetryUsageService._authority_id(
                    "usage", SCOPE, result.provider_id,
                    f"{result.provider_result_id}:{index}:{kind}",
                )
                if real_services else old_ref.resource_id
            )
            row = {
                "receipt_id": receipt_id,
                "provider": result.provider_id,
                "provider_receipt_id": f"{result.provider_result_id}:{index}:{kind}",
                "lineage_id": str(invocation_id),
                "usage_kind": kind,
                "quantity": float(quantity),
                "unit": "token",
                "currency": None,
                "quality": "measured",
                "source_hash": result_hash,
                "observed_at": result.observed_at,
            }
            rows.append(row)
            refs.append(BudgetExactRef(
                resourceType="UsageReceipt",
                resourceId=receipt_id,
                revision=1,
                contentHash=canonical_hash(row, prefixed=True),
            ))
        updated_calls.append(item.model_copy(update={
            "command_hash": command_hash,
            "result_hash": result_hash,
            "reservation_ref": reservation_ref,
            "usage_receipt_refs": tuple(refs),
            "provider_request_ref": result.provider_request_ref,
        }))
        persisted[item.reservation_id] = {
            "command": command,
            "inputBytes": evidence["inputBytes"],
            "result": result,
            "outputBytes": evidence["outputBytes"],
            "invocationId": invocation_id,
        }
        usage_rows[item.reservation_id] = tuple(rows)
    proof = type(proof).model_validate(proof.model_dump(mode="json", by_alias=True) | {
        "calls": [item.model_dump(mode="json", by_alias=True) for item in updated_calls]
    })
    return NativeCase(
        proof=proof,
        manifest=manifest,
        presented=presented,
        report=report,
        event=event,
        expected_run_version=version,
        run=run,
        journal=persisted,
        usage_rows=usage_rows,
    )


def _seed_native_case(
    admin_dsn: str, case: NativeCase, *, real_budget: bool = False
) -> None:
    with psycopg.connect(admin_dsn, row_factory=dict_row) as conn:
        conn.execute(
            "INSERT INTO twa_org(id,name) VALUES('org-org','route-native-test') "
            "ON CONFLICT(id) DO NOTHING"
        )
        conn.execute(
            "INSERT INTO twa_workspace(org_id,project_id,name) "
            "VALUES('org-org','dev-project','route-native-test') "
            "ON CONFLICT(org_id,project_id) DO NOTHING"
        )
        run = case.run
        conn.execute(
            """INSERT INTO aip_eval_run(
               org_id,project_id,run_id,suite_id,suite_revision,suite_hash,
               eval_contract_ref,subject_artifact_ref,stage_attempt_ref,gate_policy_ref,
               evidence_cutoff_at,target_ref,dataset_ref,judge_ref,status,idempotency_key,
               version,created_by,created_at,started_at,finished_at)
               VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (
                *SCOPE.key, run.run_id, run.suite_ref.asset_id, int(run.suite_ref.revision),
                run.suite_ref.content_hash, _optional_jsonb(run.eval_contract_ref),
                _optional_jsonb(run.subject_artifact_ref),
                _optional_jsonb(run.stage_attempt_ref),
                _optional_jsonb(run.gate_policy_ref), run.evidence_cutoff_at,
                Jsonb(_dump(run.target)), Jsonb(_dump(run.dataset)), Jsonb(_dump(run.judge)),
                run.status.value, run.idempotency_key, run.version, run.created_by,
                run.created_at, run.started_at, run.finished_at,
            ),
        )
        for sequence in range(1, case.expected_run_version + 1):
            before = None if sequence == 1 else ("queued" if sequence == 2 else "running")
            after = "queued" if sequence == 1 else "running"
            conn.execute(
                """INSERT INTO aip_eval_run_event(
                   org_id,project_id,event_id,run_id,sequence,event_type,from_status,
                   to_status,payload_hash,actor,created_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,'route-native-test',%s)""",
                (*SCOPE.key, f"route-native-initial-{sequence}", run.run_id, sequence,
                 f"run.{after}", before, after, "0" * 64,
                 run.created_at + timedelta(microseconds=sequence)),
            )
        price_ref = next(iter(case.journal.values()))["command"].budget_request.pricing_ref
        conn.execute(
            """INSERT INTO aip_model_price_snapshot_head(
               org_id,project_id,model_price_snapshot_id,current_revision)
               VALUES(%s,%s,%s,%s) ON CONFLICT DO NOTHING""",
            (*SCOPE.key, price_ref.resource_id, price_ref.revision),
        )
        conn.execute(
            """INSERT INTO aip_model_price_snapshot_revision(
               org_id,project_id,model_price_snapshot_id,revision,content_hash,lifecycle,
               payload,created_by) VALUES(%s,%s,%s,%s,%s,'active',%s,'route-native-test')
               ON CONFLICT DO NOTHING""",
            (*SCOPE.key, price_ref.resource_id, price_ref.revision,
             price_ref.content_hash.removeprefix("sha256:"),
             Jsonb({"tokenUnit": 1000,
                    "inputTokenPrice": "1.67" if real_budget else "0.1",
                    "outputTokenPrice": "1.25" if real_budget else "0.1"})),
        )
        by_reservation = {item.reservation_id: item for item in case.proof.calls}
        for reservation_id, evidence in case.journal.items():
            item = by_reservation[reservation_id]
            command, result = evidence["command"], evidence["result"]
            request = command.budget_request
            immutable_hash = "sha256:" + hashlib.sha256(
                ("native-" + str(reservation_id)).encode()
            ).hexdigest()
            conn.execute(
                """INSERT INTO aip_capability_invocation(
                   org_id,project_id,invocation_id,operation_id,invocation_key,request_hash,
                   task_ref,policy_ref,approval_ref,pricing_ref,currency,upper_bound_minor,
                   state,revision,content_hash)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'CNY',%s,'submitted',2,%s)""",
                (*SCOPE.key, evidence["invocationId"], request.operation_id,
                 request.invocation_key, request.request_hash(), Jsonb(_dump(request.task_ref)),
                 Jsonb(_dump(request.policy_ref)), Jsonb(_dump(request.approval_ref)),
                 Jsonb(_dump(request.pricing_ref)), request.upper_bound_minor, immutable_hash),
            )
            conn.execute(
                """INSERT INTO aip_budget_reservation(
                   org_id,project_id,reservation_id,invocation_id,operation_id,invocation_key,
                   task_ref,policy_ref,pricing_ref,approval_ref,currency,upper_bound_minor,
                   actual_minor,state,provider_request_receipt_ref,usage_receipt_refs,
                   request_hash,revision,content_hash)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'CNY',%s,NULL,'submitted',
                          %s,'[]'::jsonb,%s,2,%s)""",
                (*SCOPE.key, reservation_id, evidence["invocationId"], request.operation_id,
                 request.invocation_key, Jsonb(_dump(request.task_ref)),
                 Jsonb(_dump(request.policy_ref)), Jsonb(_dump(request.pricing_ref)),
                 Jsonb(_dump(request.approval_ref)), request.upper_bound_minor,
                 Jsonb(exact_ref_payload(item.provider_request_ref)), request.request_hash(),
                 immutable_hash),
            )
            if real_budget:
                provider_ref = BudgetExactRef(
                    resourceType="ProviderInstanceRevision",
                    resourceId=result.provider_id,
                    revision=1,
                    contentHash="sha256:" + "d" * 64,
                )
                provider_idempotency_hash = hashlib.sha256(
                    f"route-eval:{item.call_key}".encode()
                ).hexdigest()
                conn.execute(
                    """INSERT INTO aip_capability_provider_request_receipt(
                       org_id,project_id,request_receipt_id,invocation_id,request_hash,
                       provider_ref,provider_idempotency_hash,revision,content_hash,submitted_at)
                       VALUES(%s,%s,%s,%s,%s,%s, %s,1,%s,%s)""",
                    (*SCOPE.key, UUID(item.provider_request_ref.resource_id),
                     evidence["invocationId"], request.request_hash(),
                     Jsonb(exact_ref_payload(provider_ref)), provider_idempotency_hash,
                     item.provider_request_ref.content_hash, result.observed_at),
                )
                period_start = result.observed_at - timedelta(days=1)
                period_end = result.observed_at + timedelta(days=31)
                for kind in ("task", "daily", "pilot"):
                    account_id = f"route-{kind}-{reservation_id}"
                    conn.execute(
                        """INSERT INTO aip_budget_bucket(
                           org_id,project_id,bucket_kind,account_id,period_start,period_end,
                           currency,limit_minor,submitted_minor)
                           VALUES(%s,%s,%s,%s,%s,%s,'CNY',%s,%s)""",
                        (*SCOPE.key, kind, account_id, period_start, period_end,
                         request.upper_bound_minor, request.upper_bound_minor),
                    )
                    conn.execute(
                        """INSERT INTO aip_budget_reservation_bucket(
                           org_id,project_id,reservation_id,bucket_kind,account_id,
                           period_start,currency,reserved_minor)
                           VALUES(%s,%s,%s,%s,%s,%s,'CNY',%s)""",
                        (*SCOPE.key, reservation_id, kind, account_id, period_start,
                         request.upper_bound_minor),
                    )
            command_text, command_hash = _canonical(command)
            result_text, result_hash = _canonical(result)
            conn.execute(
                """INSERT INTO aip_route_eval_execution_command(
                   org_id,project_id,reservation_id,execution_id,case_id,purpose,call_key,
                   command_hash,command_payload,input_hash,input_bytes)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (*SCOPE.key, reservation_id, command.execution_id, command.case_id,
                 command.purpose, command.call_key, command_hash, command_text,
                 command.input_hash, evidence["inputBytes"]),
            )
            conn.execute(
                """INSERT INTO aip_route_eval_execution_result(
                   org_id,project_id,reservation_id,provider_request_ref,result_hash,
                   result_payload,output_hash,output_bytes)
                   VALUES(%s,%s,%s,%s,%s,%s::jsonb,%s,%s)""",
                (*SCOPE.key, reservation_id, Jsonb(exact_ref_payload(
                    item.provider_request_ref)), result_hash, result_text,
                 result.output_hash, evidence["outputBytes"]),
            )
        conn.commit()


class _LateFailStore(RouteEvalFinalizationProofStore):
    def persist(self, *args, **kwargs):
        super().persist(*args, **kwargs)
        raise RuntimeError("synthetic late sidecar acknowledgement failure")


def _install_native_seams(monkeypatch, case: NativeCase) -> None:
    by_reservation = {item.reservation_id: item for item in case.proof.calls}

    def record(_self, conn, scope, item, evidence, reservation):
        assert scope == SCOPE
        result = evidence["result"]
        invocation_id = str(reservation["invocation_id"])
        conn.execute(
            """INSERT INTO aip_lineage_event(
               org_id,project_id,event_id,lineage_id,root_type,root_id,sequence,
               event_type,subject_ref,artifact_ref,payload_hash,quality,occurred_at,
               observed_at,source_kind,source_id,source_hash)
               VALUES(%s,%s,%s,%s,'capability_invocation',%s,1,'model',NULL,NULL,
                      %s,'measured',%s,%s,'capability_provider_result',%s,%s)""",
            (*scope.key, "route-eval-result:" + str(item.reservation_id), invocation_id,
             invocation_id, item.result_hash, result.observed_at, result.observed_at,
             str(item.reservation_id), item.result_hash),
        )
        for row in case.usage_rows[item.reservation_id]:
            conn.execute(
                """INSERT INTO aip_usage_receipt(
                   org_id,project_id,receipt_id,provider,provider_receipt_id,lineage_id,
                   usage_kind,quantity,unit,currency,quality,source_hash,observed_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
                (*scope.key, row["receipt_id"], row["provider"],
                 row["provider_receipt_id"], row["lineage_id"], row["usage_kind"],
                 row["quantity"], row["unit"], row["currency"], row["quality"],
                 row["source_hash"], row["observed_at"]),
            )
        return item.result_hash, item.usage_receipt_refs

    class SeamBudget:
        def __init__(self, connect_factory, **_kwargs):
            self._connect = connect_factory

        def _actual_from_usage(self, _conn, _scope, reservation, _refs):
            return by_reservation[reservation["reservation_id"]].actual_minor

        def settle(self, scope, reservation_id, *, actual_minor,
                   provider_result_hash, usage_receipt_refs, evidence_refs, actor):
            del evidence_refs, actor
            item = by_reservation[UUID(str(reservation_id))]
            assert actual_minor == item.actual_minor
            assert tuple(usage_receipt_refs) == item.usage_receipt_refs
            request = case.journal[item.reservation_id]["command"].budget_request
            provider_ref = BudgetExactRef(
                resourceType="CapabilityProviderReceipt",
                resourceId=item.provider_result_id,
                revision=1,
                contentHash="sha256:" + provider_result_hash,
            )
            immutable = {
                "reservationId": str(item.reservation_id),
                "operationId": request.operation_id,
                "invocationKey": request.invocation_key,
                "requestHash": request.request_hash(),
                "state": "settled",
                "revision": item.budget_revision,
                "actualMinor": item.actual_minor,
                "providerRequestReceiptRef": exact_ref_payload(item.provider_request_ref),
                "providerReceiptRef": exact_ref_payload(provider_ref),
                "usageReceiptRefs": [
                    exact_ref_payload(ref) for ref in item.usage_receipt_refs
                ],
                "reconciliationEvidenceRef": None,
            }
            with self._connect(scope) as conn:
                cursor = conn.execute(
                    """UPDATE aip_budget_reservation
                       SET state='settled',actual_minor=%s,provider_receipt_ref=%s,
                           usage_receipt_refs=%s,
                           revision=%s,content_hash=%s,updated_at=clock_timestamp()
                       WHERE org_id=%s AND project_id=%s AND reservation_id=%s
                         AND state='submitted' AND revision=%s""",
                    (item.actual_minor,
                     Jsonb(exact_ref_payload(provider_ref)),
                     Jsonb([exact_ref_payload(ref) for ref in item.usage_receipt_refs]),
                     item.budget_revision,
                     canonical_hash(immutable, prefixed=True),
                     *scope.key, item.reservation_id, item.budget_revision - 1),
                )
                assert cursor.rowcount == 1
            return SimpleNamespace(
                state=BudgetReservationState.SETTLED,
                reservation_ref=BudgetExactRef(
                    resourceType="BudgetReservationRevision",
                    resourceId=str(item.reservation_id),
                    revision=item.budget_revision,
                    contentHash=canonical_hash(immutable, prefixed=True),
                ),
                actual_minor=item.actual_minor,
                usage_receipt_refs=item.usage_receipt_refs,
            )

    monkeypatch.setattr(finalizer.RouteEvalUsageRecorder, "record", record)
    monkeypatch.setattr(finalizer, "AipBudgetReservationStore", SeamBudget)


def _set_writer_context(conn, *, tenant=SCOPE, role="aos_runtime") -> None:
    conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE")
    if role:
        conn.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
    conn.execute(
        "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
        tenant.key,
    )


def _finish_native(dsn: str, database: str, case: NativeCase, *, store=None):
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        _set_writer_context(conn)
        result = finalizer.finish_route_eval_with_connection(
            conn,
            expected_database=database,
            scope=SCOPE,
            proof=case.proof,
            manifest_bytes=case.manifest,
            presented_cases=case.presented,
            checked_at=case.event.created_at,
            revoked_identity_ids=frozenset(),
            report=case.report,
            event=case.event,
            expected_run_version=case.expected_run_version,
            proof_store=store,
        )
        conn.commit()
        return result


def _reconcile_native(dsn: str, database: str, case: NativeCase):
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.read_only = True
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute(
            "SELECT set_config('aos.org_id',%s,true),set_config('aos.project_id',%s,true)",
            SCOPE.key,
        )
        result = reconcile_route_eval_finalization(
            conn,
            expected_database=database,
            scope=SCOPE,
            proof=case.proof,
            report=case.report,
            event=case.event,
            expected_run_version=case.expected_run_version,
        )
        conn.rollback()
        return result


def _terminal_snapshot(admin_dsn: str, case: NativeCase):
    tables = (
        "aip_lineage_event", "aip_usage_receipt", "aip_eval_run_event",
        "aip_eval_report_revision", "aip_route_eval_finalization_proof",
        "aip_route_eval_release_material",
        "aip_route_eval_finalized_call_proof",
    )
    with psycopg.connect(admin_dsn, row_factory=dict_row) as conn:
        counts = {
            table: conn.execute(
                sql.SQL("SELECT count(*) AS n FROM {} WHERE org_id=%s AND project_id=%s").format(
                    sql.Identifier(table)
                ),
                SCOPE.key,
            ).fetchone()["n"]
            for table in tables
        }
        run = conn.execute(
            "SELECT status,version,finished_at FROM aip_eval_run "
            "WHERE org_id=%s AND project_id=%s AND run_id=%s",
            (*SCOPE.key, case.run.run_id),
        ).fetchone()
        budgets = conn.execute(
            "SELECT reservation_id,state,revision,actual_minor,usage_receipt_refs "
            "FROM aip_budget_reservation WHERE org_id=%s AND project_id=%s "
            "ORDER BY reservation_id",
            SCOPE.key,
        ).fetchall()
        return counts, dict(run), [dict(row) for row in budgets]


def _insert_partial_terminal(admin_dsn: str, case: NativeCase) -> None:
    item = case.proof.calls[0]
    evidence = case.journal[item.reservation_id]
    result = evidence["result"]
    with psycopg.connect(admin_dsn) as conn:
        conn.execute(
            """INSERT INTO aip_lineage_event(
               org_id,project_id,event_id,lineage_id,root_type,root_id,sequence,
               event_type,payload_hash,quality,occurred_at,observed_at,
               source_kind,source_id,source_hash)
               VALUES(%s,%s,%s,%s,'capability_invocation',%s,1,'model',%s,'measured',
                      %s,%s,'capability_provider_result',%s,%s)""",
            (*SCOPE.key, "route-eval-result:" + str(item.reservation_id),
             str(evidence["invocationId"]), str(evidence["invocationId"]),
             item.result_hash, result.observed_at, result.observed_at,
             str(item.reservation_id), item.result_hash),
        )
        conn.commit()


def test_native_matrix_url_has_no_shared_or_business_database_fallback(monkeypatch):
    monkeypatch.delenv(ENV, raising=False)
    with pytest.raises(pytest.skip.Exception):
        _validated_admin_dsn(None)
    unsafe = (
        "postgresql://user:password@127.0.0.1:5432/aos_meta",
        "postgresql://user:password@example.com:18431/aos_test_x_ti4_test",
        "postgresql://user:password@127.0.0.1:18431/aos_meta",
    )
    for dsn in unsafe:
        with pytest.raises(NativeMatrixConfigurationError):
            _validated_admin_dsn(dsn)
    valid = (
        "postgresql://user:password@127.0.0.1:18431/"
        "aos_test_fixture_ti4_test?require_auth=scram-sha-256"
    )
    _, parts = _validated_admin_dsn(valid)
    assert parts["dbname"] == "aos_test_fixture_ti4_test"


def test_native_case_materialization_binds_exact_reservations_and_usage_hashes():
    case = _prepare_native_case()
    assert case.run.status.value == "running"
    assert case.expected_run_version == 2
    assert len(case.proof.calls) == 2
    for item in case.proof.calls:
        evidence = case.journal[item.reservation_id]
        command = evidence["command"]
        assert command.reservation_ref == item.reservation_ref
        assert command.invocation_ref.resource_id == str(evidence["invocationId"])
        assert _canonical(command)[1] == item.command_hash
        assert _canonical(evidence["result"])[1] == item.result_hash
        rows = case.usage_rows[item.reservation_id]
        assert len(rows) == len(item.usage_receipt_refs) == 2
        assert [canonical_hash(row, prefixed=True) for row in rows] == [
            ref.content_hash for ref in item.usage_receipt_refs
        ]


def test_native_clone_exposes_exact_scram_serializable_and_read_only_context(native_clone):
    dsn, _, database, login, _ = native_clone
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE")
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute(
            "SELECT set_config('aos.org_id','org-org',true),"
            "set_config('aos.project_id','dev-project',true)"
        )
        row = conn.execute(
            "SELECT current_database() AS database,session_user AS login,"
            "current_user AS role,current_setting('transaction_isolation') AS isolation,"
            "current_setting('transaction_read_only') AS readonly,"
            "current_setting('aos.org_id',true) AS org_id,"
            "current_setting('aos.project_id',true) AS project_id"
        ).fetchone()
        assert row == {
            "database": database, "login": login, "role": "aos_runtime",
            "isolation": "serializable", "readonly": "off",
            "org_id": "org-org", "project_id": "dev-project",
        }
        assert conn.pgconn.used_password is True
        assert conn.info.get_parameters().get("require_auth") == "scram-sha-256"
        conn.rollback()

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.read_only = True
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute(
            "SELECT set_config('aos.org_id','org-org',true),"
            "set_config('aos.project_id','dev-project',true)"
        )
        row = conn.execute(
            "SELECT current_database() AS database,current_user AS role,"
            "current_setting('transaction_isolation') AS isolation,"
            "current_setting('transaction_read_only') AS readonly"
        ).fetchone()
        assert row == {
            "database": database, "role": "aos_runtime",
            "isolation": "repeatable read", "readonly": "on",
        }
        conn.rollback()


def test_native_committed_result_reconciles_complete_after_writer_connection_closes(
    native_clone, monkeypatch,
):
    dsn, admin_dsn, database, _, _ = native_clone
    case = _prepare_native_case()
    _seed_native_case(admin_dsn, case)
    _install_native_seams(monkeypatch, case)
    assert _finish_native(dsn, database, case) == case.proof
    # The caller now has no writer connection or return channel.  Recovery is
    # read-only and must not invoke the finalizer a second time.
    result = _reconcile_native(dsn, database, case)
    assert result.state == "COMPLETE" and result.proof == case.proof


def test_native_real_usage_and_budget_services_settle_exact_combination(native_clone):
    dsn, admin_dsn, database, _, _ = native_clone
    case = _prepare_native_case(real_services=True)
    _seed_native_case(admin_dsn, case, real_budget=True)
    assert _finish_native(dsn, database, case) == case.proof
    assert _reconcile_native(dsn, database, case).state == "COMPLETE"

    with psycopg.connect(admin_dsn, row_factory=dict_row) as conn:
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_usage_receipt "
            "WHERE org_id=%s AND project_id=%s", SCOPE.key,
        ).fetchone()["n"] == 4
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_capability_provider_receipt "
            "WHERE org_id=%s AND project_id=%s AND outcome='completed'", SCOPE.key,
        ).fetchone()["n"] == 2
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_budget_usage_settlement "
            "WHERE org_id=%s AND project_id=%s", SCOPE.key,
        ).fetchone()["n"] == 4
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_budget_reservation_event "
            "WHERE org_id=%s AND project_id=%s "
            "AND from_state='submitted' AND to_state='settled'", SCOPE.key,
        ).fetchone()["n"] == 2
        buckets = conn.execute(
            "SELECT bucket_kind,submitted_minor,settled_minor "
            "FROM aip_budget_bucket WHERE org_id=%s AND project_id=%s", SCOPE.key,
        ).fetchall()
        assert len(buckets) == 6
        assert {row["bucket_kind"] for row in buckets} == {"task", "daily", "pilot"}
        assert all(
            row["submitted_minor"] == 0 and row["settled_minor"] == 2
            for row in buckets
        )


def test_native_report_proof_reader_rechecks_terminal_snapshot_after_writer_closes(
    native_clone,
):
    dsn, admin_dsn, database, _, _ = native_clone
    case = _prepare_native_case(real_services=True)
    _seed_native_case(admin_dsn, case, real_budget=True)
    assert _finish_native(dsn, database, case) == case.proof

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.read_only = True
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute(
            "SELECT set_config('aos.org_id','org-org',true),"
            "set_config('aos.project_id','dev-project',true)"
        )
        verified = read_verified_route_eval_report_from_persistence(
            conn,
            scope=SCOPE,
            report=case.report,
        )
        assert verified.report_id == case.report.report_id
        assert verified.report_hash == case.report.content_hash
        assert verified.proof == case.proof
        conn.rollback()


def test_native_release_material_is_exact_runtime_read_only_and_tenant_scoped(
    native_clone, monkeypatch,
):
    dsn, admin_dsn, database, _, _ = native_clone
    case = _prepare_native_case()
    _seed_native_case(admin_dsn, case)
    _install_native_seams(monkeypatch, case)
    assert _finish_native(dsn, database, case) == case.proof

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.read_only = True
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute(
            "SELECT set_config('aos.org_id','org-org',true),"
            "set_config('aos.project_id','dev-project',true)"
        )
        row = conn.execute(
            "SELECT manifest_hash,manifest_payload "
            "FROM aip_route_eval_release_material WHERE execution_id=%s",
            (case.proof.execution_id,),
        ).fetchone()
        assert row == {
            "manifest_hash": case.proof.manifest_hash,
            "manifest_payload": case.manifest,
        }
        conn.rollback()

    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        conn.read_only = True
        conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        conn.execute("SET LOCAL ROLE aos_runtime")
        conn.execute(
            "SELECT set_config('aos.org_id','dev-org',true),"
            "set_config('aos.project_id','dev-project',true)"
        )
        assert conn.execute(
            "SELECT count(*) AS n FROM aip_route_eval_release_material"
        ).fetchone()["n"] == 0
        conn.rollback()

    statements = (
        ("INSERT INTO aip_route_eval_release_material(org_id,project_id,execution_id,"
         "manifest_hash,manifest_payload) VALUES('org-org','dev-project','other',%s,%s)",
         (case.proof.manifest_hash, case.manifest)),
        ("UPDATE aip_route_eval_release_material SET manifest_payload=manifest_payload "
         "WHERE execution_id=%s", (case.proof.execution_id,)),
        ("DELETE FROM aip_route_eval_release_material WHERE execution_id=%s",
         (case.proof.execution_id,)),
        ("TRUNCATE aip_route_eval_release_material", ()),
    )
    for statement, params in statements:
        with psycopg.connect(dsn, row_factory=dict_row) as conn:
            conn.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE READ WRITE")
            conn.execute("SET LOCAL ROLE aos_runtime")
            conn.execute(
                "SELECT set_config('aos.org_id','org-org',true),"
                "set_config('aos.project_id','dev-project',true)"
            )
            with pytest.raises(psycopg.errors.InsufficientPrivilege):
                conn.execute(statement, params)
            conn.rollback()


def test_native_late_sidecar_failure_rolls_back_every_terminal_fact(
    native_clone, monkeypatch,
):
    dsn, admin_dsn, database, _, _ = native_clone
    case = _prepare_native_case()
    _seed_native_case(admin_dsn, case)
    before = _terminal_snapshot(admin_dsn, case)
    _install_native_seams(monkeypatch, case)
    with pytest.raises(finalizer.RouteEvalAtomicFinalizationConflict):
        _finish_native(dsn, database, case, store=_LateFailStore())
    assert _terminal_snapshot(admin_dsn, case) == before
    assert _reconcile_native(dsn, database, case).state == "UNKNOWN"


def test_native_partial_terminal_fact_reconciles_contradictory(native_clone):
    dsn, admin_dsn, database, _, _ = native_clone
    case = _prepare_native_case()
    _seed_native_case(admin_dsn, case)
    _insert_partial_terminal(admin_dsn, case)
    assert _reconcile_native(dsn, database, case).state == "CONTRADICTORY"


@pytest.mark.parametrize("fault", ["tenant", "role"])
def test_native_wrong_context_rejects_before_any_terminal_write(
    native_clone, monkeypatch, fault,
):
    dsn, admin_dsn, database, _, _ = native_clone
    case = _prepare_native_case()
    _seed_native_case(admin_dsn, case)
    before = _terminal_snapshot(admin_dsn, case)
    _install_native_seams(monkeypatch, case)
    with psycopg.connect(dsn, row_factory=dict_row) as conn:
        _set_writer_context(
            conn,
            tenant=TenantScope("dev-org", "dev-project") if fault == "tenant" else SCOPE,
            role=None if fault == "role" else "aos_runtime",
        )
        with pytest.raises(finalizer.RouteEvalAtomicFinalizationConflict):
            finalizer.finish_route_eval_with_connection(
                conn,
                expected_database=database,
                scope=SCOPE,
                proof=case.proof,
                manifest_bytes=case.manifest,
                presented_cases=case.presented,
                checked_at=case.event.created_at,
                revoked_identity_ids=frozenset(),
                report=case.report,
                event=case.event,
                expected_run_version=case.expected_run_version,
            )
        conn.rollback()
    assert _terminal_snapshot(admin_dsn, case) == before
