#!/usr/bin/env python3
"""Perform exactly one journaled A0-V Provider health call and record metadata."""

from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import os
import re
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Sequence


ROOT = Path(__file__).resolve().parents[1]
API_ROOT = ROOT / "services/aos-api"
FIRST_INSTALLER = ROOT / "scripts/a0v_canonical_ecommerce_first_install.py"
RECOVERY_ROOT = ROOT.parent / ".aos-recovery-20260910"
ORG_ID = "org-org"
PROJECT_ID = "dev-project"
CANARY_ORG_ID = "dev-org"
CANARY_PROJECT_ID = "dev-project"
ACTOR = "a0v-real-text-provider-health"
APPROVAL_REF = "approval:AOS-000573:A0-V-local-readonly"
PROVIDER_ID = "a0v-agnes-text-readonly-dev"
PROVIDER_REVISION = 1
NETWORK_ID = "a0v-ecommerce-network-v1"
NETWORK_REVISION = 1
PROVIDER_MODEL_ID = "agnes-2.5-flash"
PROMPT = "请仅回复：健康检查通过。"
ATTEMPT_ID = "a0v-provider-health-attempt-v2"


class ProviderHealthBlocked(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--database-name")
    parser.add_argument("--docker-context", default="colima-aos-extension")
    parser.add_argument("--database-container", default="aos-a0v-recovery-pg")
    parser.add_argument(
        "--state-dir",
        type=Path,
        default=RECOVERY_ROOT / "state/a0v-real-text-provider-health",
    )
    parser.add_argument("--output", type=Path)
    parser.add_argument("--attempt-id", default=ATTEMPT_ID)
    return parser.parse_args(argv)


def _load_first_installer() -> Any:
    spec = importlib.util.spec_from_file_location("a0v_first_install", FIRST_INSTALLER)
    if spec is None or spec.loader is None:
        raise ProviderHealthBlocked("FIRST_INSTALLER_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scoped_factory(connect: Any):
    def scoped(_scope: Any = None):
        return connect()

    return scoped


def _exact_ref(asset_type: str, item: Any, identity: str) -> Any:
    from aos_api.aip_agent_registry_contracts import VersionedAssetRef

    return VersionedAssetRef(
        assetType=asset_type,
        assetId=getattr(item, identity),
        revision=item.revision,
        contentHash=item.content_hash,
    )


def _journal_path(state_dir: Path, attempt_id: str = ATTEMPT_ID) -> Path:
    if not isinstance(attempt_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,99}", attempt_id):
        raise ProviderHealthBlocked("HEALTH_ATTEMPT_ID_INVALID")
    name = "attempt-v2.json" if attempt_id == ATTEMPT_ID else attempt_id + ".json"
    return state_dir.resolve() / name


def _read_journal(state_dir: Path, attempt_id: str = ATTEMPT_ID) -> dict[str, Any] | None:
    path = _journal_path(state_dir, attempt_id)
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise ProviderHealthBlocked("HEALTH_ATTEMPT_JOURNAL_INVALID") from None
    if not isinstance(value, dict) or value.get("attemptId") != attempt_id:
        raise ProviderHealthBlocked("HEALTH_ATTEMPT_JOURNAL_INVALID")
    return value


def _write_journal(state_dir: Path, payload: dict[str, Any]) -> None:
    state_dir = state_dir.resolve()
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(state_dir, 0o700)
    path = _journal_path(state_dir, payload.get("attemptId"))
    temporary = path.with_name(path.name + ".tmp-" + uuid.uuid4().hex)
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str) + "\n"
    try:
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        os.chmod(path, 0o600)
    except OSError:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass
        raise ProviderHealthBlocked("HEALTH_ATTEMPT_JOURNAL_WRITE_FAILED") from None


def _inventory(connect: Any) -> dict[str, Any]:
    with connect() as conn:
        identity = conn.execute(
            "SELECT current_database() AS database, clock_timestamp() AS observed_at"
        ).fetchone()
        if identity is None or identity["database"] != "aos_meta_head":
            raise ProviderHealthBlocked("DATABASE_IDENTITY_MISMATCH")
        provider = conn.execute(
            "SELECT count(*) AS n FROM aip_provider_instance_revision "
            "WHERE org_id=%s AND project_id=%s AND provider_instance_id=%s AND revision=%s AND lifecycle='active'",
            (ORG_ID, PROJECT_ID, PROVIDER_ID, PROVIDER_REVISION),
        ).fetchone()
        health = conn.execute(
            "SELECT count(*) AS n FROM aip_provider_health_observation "
            "WHERE org_id=%s AND project_id=%s AND status='healthy' "
            "AND provider_ref->>'assetId'=%s "
            "AND (provider_ref->>'revision')::integer=%s "
            "AND observed_at<=clock_timestamp() AND expires_at>clock_timestamp()",
            (ORG_ID, PROJECT_ID, PROVIDER_ID, PROVIDER_REVISION),
        ).fetchone()
        health_total = conn.execute(
            "SELECT count(*) AS n FROM aip_provider_health_observation "
            "WHERE org_id=%s AND project_id=%s "
            "AND provider_ref->>'assetId'=%s "
            "AND (provider_ref->>'revision')::integer=%s",
            (ORG_ID, PROJECT_ID, PROVIDER_ID, PROVIDER_REVISION),
        ).fetchone()
        canary = conn.execute(
            "SELECT "
            "(SELECT count(*) FROM aip_provider_instance_revision WHERE org_id=%s AND project_id=%s) + "
            "(SELECT count(*) FROM aip_provider_health_observation WHERE org_id=%s AND project_id=%s) AS n",
            (CANARY_ORG_ID, CANARY_PROJECT_ID, CANARY_ORG_ID, CANARY_PROJECT_ID),
        ).fetchone()
    result = {
        "activeExactProviderCount": int(provider["n"]),
        "currentHealthyObservationCount": int(health["n"]),
        "exactHealthObservationCount": int(health_total["n"]),
        "canaryProviderAndHealthCount": int(canary["n"]),
        "observedAt": identity["observed_at"],
    }
    if result["activeExactProviderCount"] != 1:
        raise ProviderHealthBlocked("EXACT_PROVIDER_AUTHORITY_UNAVAILABLE")
    if result["canaryProviderAndHealthCount"]:
        raise ProviderHealthBlocked("CANARY_PROVIDER_AUTHORITY_NOT_EMPTY")
    return result


def preflight() -> dict[str, Any]:
    return {
        "outcome": "PREFLIGHT_GREEN",
        "mode": "preflight",
        "scope": {"orgId": ORG_ID, "projectId": PROJECT_ID},
        "provider": {"assetId": PROVIDER_ID, "revision": PROVIDER_REVISION},
        "networkPolicy": {"assetId": NETWORK_ID, "revision": NETWORK_REVISION},
        "approvalRef": APPROVAL_REF,
        "providerModelId": PROVIDER_MODEL_ID,
        "probeCount": 1,
        "maxAttempts": 1,
        "timeoutMs": 10_000,
        "maxOutputTokens": 32,
        "outputPolicy": "metadata-only",
    }


def apply(args: argparse.Namespace) -> dict[str, Any]:
    attempt_id = args.attempt_id
    _journal_path(args.state_dir, attempt_id)
    if args.database_name != "aos_meta_head":
        raise ProviderHealthBlocked("EXPLICIT_ISOLATED_DATABASE_REQUIRED")
    installer = _load_first_installer()
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    connect = installer.container_database_connect_factory(
        context=args.docker_context,
        container=args.database_container,
        database_name=args.database_name,
    )
    before = _inventory(connect)
    sys.path.insert(0, str(API_ROOT))
    try:
        from aos_api.aip_model_runtime_contracts import ProviderHealthObservation
        from aos_api.aip_model_runtime_store import AipModelRuntimeStore
        from aos_api.aip_network_policy_store import AipNetworkPolicyStore
        from aos_api.aip_r1_bootstrap_probe import (
            AipR1BootstrapProbe,
            R1BootstrapProbeBlocked,
            R1BootstrapProbeRequest,
        )
        from aos_api.aip_secret_backend import ExactSecretResolver, SecretBackendError
        from aos_api.tenant_scope import TenantScope
        from aos_api.aip_runtime_guard_policy_store import AipRuntimeGuardPolicyStore

        scope = TenantScope(ORG_ID, PROJECT_ID)
        factory = _scoped_factory(connect)
        store = AipModelRuntimeStore(factory)
        provider = store.get_provider(scope, PROVIDER_ID, PROVIDER_REVISION)
        network = AipNetworkPolicyStore(factory).get(scope, NETWORK_ID, NETWORK_REVISION)
        provider_ref = _exact_ref(
            "ProviderInstanceRevision", provider, "provider_instance_id"
        )
        network_ref = _exact_ref("NetworkPolicyRevision", network, "policy_id")
        current = [
            item
            for item in store.list_latest_provider_health(scope)
            if item.provider == provider_ref
            and item.status == "healthy"
            and item.observed_at <= before["observedAt"] < item.expires_at
        ]
        if current:
            observation = current[0]
            provider_calls = 0
            total_tokens = 0
            latency_ms = observation.p50_latency_ms
        else:
            journal = _read_journal(args.state_dir, attempt_id)
            if journal is not None:
                raise ProviderHealthBlocked("HEALTH_ATTEMPT_ALREADY_CONSUMED")
            secret_resolver = ExactSecretResolver()
            try:
                secret = secret_resolver.resolve(scope, provider)
            except SecretBackendError as exc:
                raise ProviderHealthBlocked(f"secret_{exc.code}") from None
            if not secret:
                raise ProviderHealthBlocked("secret_keychain_empty")
            del secret
            _write_journal(
                args.state_dir,
                {
                    "attemptId": attempt_id,
                    "status": "submitted",
                    "provider": provider_ref.model_dump(mode="json", by_alias=True),
                    "networkPolicy": network_ref.model_dump(mode="json", by_alias=True),
                    "approvalRef": APPROVAL_REF,
                    "submittedAt": datetime.now(UTC),
                    "maxAttempts": 1,
                    "maxOutputTokens": 32,
                },
            )
            probe = AipR1BootstrapProbe(
                model_store=store,
                guard_store=AipRuntimeGuardPolicyStore(factory),
                network_store=AipNetworkPolicyStore(factory),
                secret_resolver=secret_resolver,
                allowed_approval_refs=frozenset({APPROVAL_REF}),
            )
            try:
                result = probe.run(
                    scope,
                    R1BootstrapProbeRequest(
                        provider=provider_ref,
                        networkPolicy=network_ref,
                        providerModelId=PROVIDER_MODEL_ID,
                        dataClassification="public_catalog",
                        prompt=PROMPT,
                        expectedResponseBehavior="non_empty",
                        approvalRef=APPROVAL_REF,
                        maxOutputTokens=32,
                    ),
                )
            except R1BootstrapProbeBlocked as exc:
                _write_journal(
                    args.state_dir,
                    {
                        "attemptId": attempt_id,
                        "status": "blocked",
                        "reasonCode": exc.code,
                        "provider": provider_ref.model_dump(mode="json", by_alias=True),
                        "completedAt": datetime.now(UTC),
                        "providerCalls": 1,
                    },
                )
                raise ProviderHealthBlocked(exc.code) from None
            observation = ProviderHealthObservation(
                tenant={"orgId": ORG_ID, "projectId": PROJECT_ID},
                observationId=f"a0v-health-{result.observed_at:%Y%m%d%H%M%S%f}",
                provider=provider_ref,
                status="healthy",
                availabilityPct=100,
                p50LatencyMs=result.latency_ms,
                observedAt=result.observed_at,
                expiresAt=result.observed_at + timedelta(minutes=15),
            )
            observation = store.record_health(
                scope,
                ACTOR,
                attempt_id,
                observation,
            )
            provider_calls = 1
            total_tokens = result.total_tokens
            latency_ms = result.latency_ms
            _write_journal(
                args.state_dir,
                {
                    "attemptId": attempt_id,
                    "status": "completed",
                    "observationId": observation.observation_id,
                    "provider": provider_ref.model_dump(mode="json", by_alias=True),
                    "completedAt": datetime.now(UTC),
                    "providerCalls": 1,
                },
            )
    finally:
        sys.path.remove(str(API_ROOT))
    after = _inventory(connect)
    return {
        "outcome": "A0V_REAL_TEXT_PROVIDER_HEALTH_GREEN",
        "mode": "apply",
        "scope": {"orgId": ORG_ID, "projectId": PROJECT_ID},
        "observation": {
            "observationId": observation.observation_id,
            "provider": observation.provider.model_dump(mode="json", by_alias=True),
            "status": observation.status,
            "observedAt": observation.observed_at,
            "expiresAt": observation.expires_at,
            "p50LatencyMs": observation.p50_latency_ms,
        },
        "before": before,
        "after": after,
        "providerCalls": provider_calls,
        "healthObservationMutationCount": (
            after["exactHealthObservationCount"]
            - before["exactHealthObservationCount"]
        ),
        "totalTokens": total_tokens,
        "latencyMs": latency_ms,
        "secretPayloadReadsReported": 0,
        "promptOrAnswerBodiesReported": 0,
        "businessMutationCount": 0,
        "externalPublicationCount": 0,
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    return apply(args) if args.apply else preflight()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = run(args)
        status = 0
    except ProviderHealthBlocked as exc:
        result = {
            "outcome": "SAFE_BLOCKED",
            "reasonCode": exc.code,
            "providerCallsMayHaveOccurred": _read_journal(args.state_dir) is not None,
            "healthObservationWritten": False,
        }
        status = 2
    rendered = json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True, default=str)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return status


if __name__ == "__main__":
    raise SystemExit(main())
