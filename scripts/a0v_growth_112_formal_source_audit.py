#!/usr/bin/env python3
"""Read-only current-vs-clone authorization gap audit; never grants runtime."""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
os.environ["AOS_DOTENV_DISABLED"] = "1"
CANDIDATE_FIELDS = (
    "responsibility_plans", "runtime_policies", "data_policies", "egress_policies",
    "network_policies", "quota_policies", "budget_policies", "budgets",
)
TARGETS = {
    "current": ("colima-aos-extension", "aos-a0v-recovery-pg",
                "aos-a0v-recovery-pg-data", "18435"),
    "clone": ("colima-aos-a0v-test-only", "aos-bg00dl-isolated-pg",
              "aos-bg00dl-isolated-pg-data", "18440"),
}


class AuditBlocked(RuntimeError):
    pass


def assess_sources(*, current: dict[str, object], clone: dict[str, object],
                   current_trusts_growth112: bool,
                   credential_reference_present: bool) -> dict[str, object]:
    if set(current.get("configurationCandidates", {})) != set(CANDIDATE_FIELDS):
        raise AuditBlocked("CURRENT_CANDIDATE_SHAPE_DRIFT")
    if set(clone.get("configurationCandidates", {})) != set(CANDIDATE_FIELDS):
        raise AuditBlocked("CLONE_CANDIDATE_SHAPE_DRIFT")
    reasons = []
    if clone["growth112Published"] != 1:
        reasons.append("CLONE_SUCCESSOR_MISSING")
    if current["growth112Published"] != 1:
        reasons.append("CURRENT_RELEASE_MISSING")
    if not current_trusts_growth112:
        reasons.append("CURRENT_TRUST_ROOT_MISSING")
    if current["distinctPositiveTenantMembers"] < 2:
        reasons.append("INDEPENDENT_CHECKER_MISSING")
    if not credential_reference_present:
        reasons.append("THREE_PLANE_CREDENTIAL_REFERENCE_MISSING")
    if current["hostIdentity"] != 1:
        reasons.append("HOST_IDENTITY_MISSING")
    if current["hostAssignment"] != 1:
        reasons.append("HOST_ASSIGNMENT_MISSING")
    if any(current["configurationCandidates"][name] < 1 for name in CANDIDATE_FIELDS):
        reasons.append("CONFIGURATION_CANDIDATES_MISSING")
    # Counts and paths cannot prove precise issuer, checker, revocation or binding.
    reasons.append("FORMAL_AUTHORIZATION_NOT_PROVEN")
    return {"formalReady": False, "reasons": reasons}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise AuditBlocked("MODULE_UNAVAILABLE")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _check_container(label: str) -> None:
    context, container, volume, port = TARGETS[label]
    result = subprocess.run(["docker", "--context", context, "inspect", container],
                            capture_output=True, text=True, check=True)
    info = json.loads(result.stdout)[0]
    mounts = info.get("Mounts") or []
    data_mounts = [item for item in mounts
                   if item.get("Destination") == "/var/lib/postgresql/data"]
    binding = ((info.get("NetworkSettings") or {}).get("Ports") or {}).get("5432/tcp") or []
    if (info.get("State", {}).get("Running") is not True
            or len(data_mounts) != 1 or data_mounts[0].get("Name") != volume
            or any(item.get("RW") is True for item in mounts if item not in data_mounts)
            or len(binding) != 1 or binding[0].get("HostIp") != "127.0.0.1"
            or binding[0].get("HostPort") != port):
        raise AuditBlocked(f"{label.upper()}_PHYSICAL_TARGET_DRIFT")


def _read_control(label: str, parameters: dict[str, object]) -> dict[str, object]:
    import psycopg
    from psycopg.rows import dict_row
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    try:
        from aos_api.extension_runtime.runtime_configuration_candidates import read_candidates
        from aos_api.tenant_scope import TenantScope

        with psycopg.connect(**parameters, row_factory=dict_row) as conn:
            conn.read_only = True
            if (conn.info.dbname != "aos_current_preview_20260927"
                    or conn.info.host != "127.0.0.1"
                    or str(conn.info.port) != TARGETS[label][3]):
                raise AuditBlocked("DATABASE_NAME_DRIFT")
            version = conn.execute("SELECT version_num FROM alembic_version").fetchall()
            if [row["version_num"] for row in version] != ["a0v_118"]:
                raise AuditBlocked("SCHEMA_VERSION_DRIFT")
            scope = TenantScope(org_id="org-org", project_id="dev-project")
            candidates = read_candidates(conn, scope).counts
            members = conn.execute("""SELECT count(DISTINCT subject) AS n FROM meta_membership
                WHERE org_id=%s AND project_id=%s""", scope.key).fetchone()["n"]
            growth = conn.execute("""SELECT count(*) AS n FROM asset_bundle_version v
                JOIN asset_bundle b ON b.bundle_pk=v.bundle_pk
                WHERE b.bundle_id='solution.ecommerce.growth'
                  AND v.version='1.12.0' AND v.status='published'""").fetchone()["n"]
            identity = conn.execute("SELECT count(*) AS n FROM extension_runtime_host_identity").fetchone()["n"]
            assignment = conn.execute("""SELECT count(*) AS n FROM extension_runtime_host_assignment
                WHERE org_id=%s AND project_id=%s AND state='assigned'""", scope.key).fetchone()["n"]
            control = {name: conn.execute(f"SELECT count(*) AS n FROM {name}").fetchone()["n"]
                       for name in ("bundle_installation", "extension_runtime_operation",
                                    "extension_runtime_binding", "extension_runtime_configuration")}
            return {"target": label, "database": conn.info.dbname, "version": version[0]["version_num"],
                    "growth112Published": growth, "distinctPositiveTenantMembers": members,
                    "hostIdentity": identity, "hostAssignment": assignment,
                    "configurationCandidates": candidates, "controlRows": control}
    finally:
        sys.path.remove(str(ROOT / "services/aos-api"))


def audit(*, current_receipt: Path, successor_receipt: Path,
          credential_reference: Path | None = None) -> dict[str, object]:
    _check_container("current")
    _check_container("clone")
    signed = _load(ROOT / "scripts/a0v_growth_112_successor_clone.py", "bg00dn_signed_reader")
    current_sign = signed.check_signed_receipt(current_receipt, expected_growth="1.11.0")
    successor_sign = signed.check_signed_receipt(successor_receipt, expected_growth="1.12.0")
    sys.path.insert(0, str(ROOT / "services/aos-api"))
    try:
        from aos_api.asset_registry.signature import FileTrustRootProvider
        root = FileTrustRootProvider(current_sign["trust_path"]).snapshot().get_trust_root(
            publisher="aos", key_id=successor_sign["receipt"]["keyId"])
    finally:
        sys.path.remove(str(ROOT / "services/aos-api"))
    bootstrap = _load(ROOT / "scripts/a0v_current_preview_bootstrap.py", "bg00dn_current_bootstrap")
    current = _read_control("current", bootstrap._connection_parameters())
    clone = _read_control("clone", signed._clone_connection_parameters())
    decision = assess_sources(current=current, clone=clone,
                              current_trusts_growth112=root is not None,
                              credential_reference_present=(credential_reference is not None
                                                            and credential_reference.is_absolute()
                                                            and credential_reference.is_file()))
    return {"outcome": "CURRENT_FORMAL_SOURCE_AUDIT_SAFE_BLOCKED", "current": current,
            "clone": clone, "currentTrustsGrowth112": root is not None,
            "credentialReferencePresent": credential_reference is not None
            and credential_reference.is_absolute() and credential_reference.is_file(),
            **decision, "effects": 0}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--current-signed-receipt", type=Path, required=True)
    parser.add_argument("--successor-signed-receipt", type=Path, required=True)
    parser.add_argument("--credential-reference", type=Path)
    args = parser.parse_args()
    print(json.dumps(audit(current_receipt=args.current_signed_receipt,
                           successor_receipt=args.successor_signed_receipt,
                           credential_reference=args.credential_reference), sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(json.dumps({"outcome": "SAFE_BLOCKED",
                          "reasonCode": str(exc) if isinstance(exc, AuditBlocked)
                          else type(exc).__name__}, sort_keys=True))
        raise SystemExit(2) from None
