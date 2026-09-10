#!/usr/bin/env python3
"""Collect the A0-V readiness surface through loopback GET requests only."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


POSITIVE_TENANT = ("org-org", "dev-project")
CANARY_TENANT = ("dev-org", "dev-project")
MAX_BODY_BYTES = 2 * 1024 * 1024
SENSITIVE_KEY = re.compile(
    r"(?:authorization|password|passwd|secret|token|api[_-]?key|credential)",
    re.IGNORECASE,
)
BEARER = re.compile(r"(?i)bearer\s+[a-z0-9._~+/=-]+")
DSN_PASSWORD = re.compile(r"(postgres(?:ql)?://[^:/\s]+:)[^@/\s]+(@)")


READS = (
    ("sourceReadiness", "/v1/data/source-readiness", True),
    ("workshopSourceReadiness", "/v1/ecommerce-workshop/source-readiness", True),
    ("agentRegistry", "/v1/aip/agent-registry", True),
    ("agentRuntimeReadiness", "/v1/aip/agent-registry/runtime-readiness", True),
    ("capabilityCatalog", "/v1/aip/capability-catalog", True),
    ("modelRuntime", "/v1/aip/model-runtime/overview", True),
    ("modelChain", "/v1/aip/model-runtime/chain-overview", True),
    ("modelCost", "/v1/aip/model-runtime/cost-overview", True),
    ("bundleInstallations", "/v1/bundle-installations?limit=100&offset=0", True),
    (
        "productionContexts",
        "/v1/aip/production-contracts/production-contexts",
        True,
    ),
    (
        "productionStartDecisions",
        "/v1/aip/production-contracts/production-start-decisions",
        True,
    ),
    (
        "responsibilityPlans",
        "/v1/aip/production-contracts/responsibility-plans",
        True,
    ),
    ("stageTemplates", "/v1/aip/production-contracts/stage-templates", True),
    ("taskBriefs", "/v1/aip/production-contracts/task-briefs", True),
)


def _redact(value: Any, key: str = "") -> Any:
    if SENSITIVE_KEY.search(key):
        return "<redacted>"
    if isinstance(value, dict):
        return {str(k): _redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(item) for item in value]
    if isinstance(value, str):
        return DSN_PASSWORD.sub(r"\1<redacted>\2", BEARER.sub("Bearer <redacted>", value))
    return value


def _request(
    base_url: str,
    path: str,
    *,
    tenant: tuple[str, str] | None,
    authenticated: bool,
) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if authenticated:
        headers["Authorization"] = "Bearer dev"
    if tenant is not None:
        headers["X-Org-Id"], headers["X-Project-Id"] = tenant
    request = urllib.request.Request(base_url + path, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            status = response.status
            raw = response.read(MAX_BODY_BYTES + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read(MAX_BODY_BYTES + 1)
    except Exception as exc:
        return {
            "method": "GET",
            "path": path,
            "httpStatus": None,
            "errorType": type(exc).__name__,
            "bodySha256": None,
            "body": None,
        }
    if len(raw) > MAX_BODY_BYTES:
        raise RuntimeError(f"response exceeds {MAX_BODY_BYTES} bytes: {path}")
    try:
        body: Any = json.loads(raw)
    except json.JSONDecodeError:
        body = {"nonJsonBody": raw.decode("utf-8", errors="replace")}
    return {
        "method": "GET",
        "path": path,
        "httpStatus": status,
        "bodySha256": hashlib.sha256(raw).hexdigest(),
        "body": _redact(body),
    }


def _collection_size(body: Any) -> int | None:
    if isinstance(body, list):
        return len(body)
    if not isinstance(body, dict):
        return None
    if isinstance(body.get("count"), int):
        return body["count"]
    if isinstance(body.get("total"), int):
        return body["total"]
    if isinstance(body.get("items"), list):
        return len(body["items"])
    return None


def _non_empty_model_sections(body: Any) -> dict[str, int]:
    if not isinstance(body, dict):
        return {}
    result: dict[str, int] = {}
    for key in (
        "providers",
        "models",
        "routes",
        "resolutions",
        "healthObservations",
        "capacityPools",
        "priceSnapshots",
        "evalGates",
        "budgets",
        "quotas",
        "usage",
        "chains",
    ):
        value = body.get(key)
        if isinstance(value, list):
            result[key] = len(value)
    return result


def _tenant_claim(body: Any) -> tuple[str, str] | None:
    if not isinstance(body, dict) or not isinstance(body.get("tenant"), dict):
        return None
    tenant = body["tenant"]
    org = tenant.get("orgId") or tenant.get("org_id")
    project = tenant.get("projectId") or tenant.get("project_id")
    if isinstance(org, str) and isinstance(project, str):
        return org, project
    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.utcoffset() is not None else None


def _status_reason(value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        return "MALFORMED_READINESS_BODY"
    return f"STATUS_{value.strip().upper()}"


def _semantic_readiness_blockers(
    positive: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    blockers: list[dict[str, Any]] = []

    for name in ("sourceReadiness", "workshopSourceReadiness"):
        observed = positive[name]
        if observed.get("httpStatus") != 200:
            continue
        body = observed.get("body")
        if not isinstance(body, dict):
            blockers.append({"gate": f"{name}.status", "reason": "MALFORMED_READINESS_BODY"})
            continue
        status = body.get("status")
        sources = body.get("sources")
        if status != "ready":
            blockers.append({"gate": f"{name}.status", "reason": _status_reason(status)})
        if not isinstance(sources, list) or len(sources) != 12:
            blockers.append({"gate": f"{name}.sources", "reason": "EXPECTED_12_SOURCES"})
        elif any(not isinstance(item, dict) or item.get("status") != "ready" for item in sources):
            blockers.append({"gate": f"{name}.sources", "reason": "SOURCE_NOT_READY"})

    expected_agent_stats = {
        "definitionCount": 6,
        "installedCount": 6,
        "runnableCount": 6,
        "skillDefinitionCount": 37,
        "capabilityDefinitionCount": 10,
    }
    observed = positive["agentRegistry"]
    if observed.get("httpStatus") == 200:
        body = observed.get("body")
        stats = body.get("stats") if isinstance(body, dict) else None
        if not isinstance(stats, dict):
            blockers.append({"gate": "agentRegistry.stats", "reason": "MALFORMED_READINESS_BODY"})
        else:
            for key, expected in expected_agent_stats.items():
                if stats.get(key) != expected:
                    blockers.append(
                        {
                            "gate": f"agentRegistry.stats.{key}",
                            "reason": "COUNT_MISMATCH",
                            "expected": expected,
                            "observed": stats.get(key),
                        }
                    )

    observed = positive["agentRuntimeReadiness"]
    if observed.get("httpStatus") == 200:
        body = observed.get("body")
        catalog = body.get("catalog") if isinstance(body, dict) else None
        stats = catalog.get("stats") if isinstance(catalog, dict) else None
        items = catalog.get("items") if isinstance(catalog, dict) else None
        if not isinstance(stats, dict) or not isinstance(items, list):
            blockers.append(
                {"gate": "agentRuntimeReadiness.catalog", "reason": "MALFORMED_READINESS_BODY"}
            )
        else:
            for key, expected in expected_agent_stats.items():
                if stats.get(key) != expected:
                    blockers.append(
                        {
                            "gate": f"agentRuntimeReadiness.stats.{key}",
                            "reason": "COUNT_MISMATCH",
                            "expected": expected,
                            "observed": stats.get(key),
                        }
                    )
            if len(items) != 6 or any(
                not isinstance(item, dict)
                or item.get("runtimeReadiness") != "runnable"
                or item.get("blockers") != []
                for item in items
            ):
                blockers.append(
                    {"gate": "agentRuntimeReadiness.items", "reason": "AGENT_NOT_RUNNABLE"}
                )

    observed = positive["capabilityCatalog"]
    if observed.get("httpStatus") == 200:
        body = observed.get("body")
        if not isinstance(body, dict):
            blockers.append(
                {"gate": "capabilityCatalog.counts", "reason": "MALFORMED_READINESS_BODY"}
            )
        else:
            for key in ("count", "availableCount"):
                if body.get(key) != 10:
                    blockers.append(
                        {
                            "gate": f"capabilityCatalog.{key}",
                            "reason": "COUNT_MISMATCH",
                            "expected": 10,
                            "observed": body.get(key),
                        }
                    )

    observed = positive["modelRuntime"]
    if observed.get("httpStatus") == 200:
        body = observed.get("body")
        if not isinstance(body, dict):
            blockers.append({"gate": "modelRuntime.semantic", "reason": "MALFORMED_READINESS_BODY"})
        else:
            resolutions = body.get("resolutions")
            if not isinstance(resolutions, list) or not any(
                isinstance(item, dict) and item.get("readiness") == "ready"
                for item in resolutions
            ):
                blockers.append({"gate": "modelRuntime.resolutions", "reason": "NO_READY_ROUTE"})
            generated_at = _parse_datetime(body.get("generatedAt"))
            health = body.get("healthObservations")
            healthy = (
                isinstance(health, list)
                and generated_at is not None
                and any(
                    isinstance(item, dict)
                    and item.get("status") == "healthy"
                    and (expires_at := _parse_datetime(item.get("expiresAt"))) is not None
                    and expires_at > generated_at
                    for item in health
                )
            )
            if not healthy:
                blockers.append(
                    {"gate": "modelRuntime.healthObservations", "reason": "NO_FRESH_HEALTHY_PROVIDER"}
                )

    observed = positive["modelChain"]
    if observed.get("httpStatus") == 200:
        body = observed.get("body")
        chains = body.get("chains") if isinstance(body, dict) else None
        ready_chain = isinstance(chains, list) and any(
            isinstance(chain, dict)
            and chain.get("readiness") == "ready"
            and chain.get("controlledTrialAllowed") is True
            and isinstance(chain.get("nodes"), list)
            and len(chain["nodes"]) == 6
            and all(
                isinstance(node, dict)
                and node.get("status") == "ready"
                and node.get("blockerCode") is None
                for node in chain["nodes"]
            )
            for chain in chains
        )
        if not ready_chain:
            blockers.append({"gate": "modelChain.chains", "reason": "NO_READY_CHAIN"})

    observed = positive["modelCost"]
    if observed.get("httpStatus") == 200:
        body = observed.get("body")
        budgets = body.get("budgets") if isinstance(body, dict) else None
        active_budget = isinstance(budgets, list) and any(
            isinstance(item, dict)
            and item.get("status") == "active"
            and item.get("currency") == "CNY"
            and item.get("hardStop") is True
            and isinstance(item.get("dailyLimitMinor"), int)
            and item["dailyLimitMinor"] > 0
            and isinstance(item.get("monthlyLimitMinor"), int)
            and item["monthlyLimitMinor"] > 0
            for item in budgets
        )
        if not active_budget:
            blockers.append({"gate": "modelCost.budgets", "reason": "NO_ACTIVE_CNY_HARD_STOP_BUDGET"})

    return blockers


def _git_head(repo: Path) -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=repo, text=True
    ).strip()


def collect(base_url: str, repo: Path) -> dict[str, Any]:
    parsed = urllib.parse.urlsplit(base_url)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise ValueError("A0-V collector only permits loopback HTTP")

    health = _request(base_url, "/v1/health", tenant=None, authenticated=False)
    positive = {
        name: _request(base_url, path, tenant=POSITIVE_TENANT, authenticated=True)
        for name, path, _critical in READS
    }
    canary = {
        name: _request(base_url, path, tenant=CANARY_TENANT, authenticated=True)
        for name, path, _critical in READS
    }
    negatives = {
        "missingBearer": _request(
            base_url,
            "/v1/aip/model-runtime/overview",
            tenant=POSITIVE_TENANT,
            authenticated=False,
        ),
        "invalidLimit": _request(
            base_url,
            "/v1/bundle-installations?limit=101&offset=0",
            tenant=POSITIVE_TENANT,
            authenticated=True,
        ),
    }

    blockers: list[dict[str, Any]] = []
    unverified: list[dict[str, Any]] = []
    if health["httpStatus"] != 200:
        blockers.append({"gate": "apiHealth", "reason": "HTTP_NOT_200"})
    for name, _path, critical in READS:
        observed = positive[name]
        if critical and observed["httpStatus"] != 200:
            body = observed.get("body") or {}
            blockers.append(
                {
                    "gate": name,
                    "reason": body.get("code", "HTTP_NOT_200")
                    if isinstance(body, dict)
                    else "HTTP_NOT_200",
                    "httpStatus": observed["httpStatus"],
                }
            )

    blockers.extend(_semantic_readiness_blockers(positive))

    for name in (
        "bundleInstallations",
        "productionContexts",
        "productionStartDecisions",
        "responsibilityPlans",
        "stageTemplates",
        "taskBriefs",
    ):
        observed = positive[name]
        size = _collection_size(observed.get("body"))
        if observed["httpStatus"] == 200 and size == 0:
            blockers.append({"gate": name, "reason": "REQUIRED_COLLECTION_EMPTY"})

    model_counts: dict[str, dict[str, int]] = {}
    for name in ("modelRuntime", "modelChain", "modelCost"):
        model_counts[name] = _non_empty_model_sections(positive[name].get("body"))
    required_model_sections = {
        "modelRuntime": ("providers", "models", "routes"),
    }
    for name, keys in required_model_sections.items():
        if positive[name]["httpStatus"] != 200:
            continue
        for key in keys:
            if model_counts[name].get(key, 0) == 0:
                blockers.append(
                    {"gate": f"{name}.{key}", "reason": "REQUIRED_COLLECTION_EMPTY"}
                )

    if negatives["missingBearer"]["httpStatus"] != 401:
        blockers.append({"gate": "missingBearer", "reason": "EXPECTED_401"})
    if negatives["invalidLimit"]["httpStatus"] not in {400, 422}:
        blockers.append({"gate": "invalidLimit", "reason": "EXPECTED_4XX"})

    tenant_claims: dict[str, dict[str, list[str] | None]] = {}
    visible_positive_resources = False
    for name in positive:
        positive_claim = _tenant_claim(positive[name].get("body"))
        canary_claim = _tenant_claim(canary[name].get("body"))
        tenant_claims[name] = {
            "positive": list(positive_claim) if positive_claim else None,
            "canary": list(canary_claim) if canary_claim else None,
        }
        positive_size = _collection_size(positive[name].get("body"))
        if isinstance(positive_size, int) and positive_size > 0:
            visible_positive_resources = True
        if positive_claim and positive_claim != POSITIVE_TENANT:
            blockers.append({"gate": f"{name}.tenant", "reason": "TENANT_MISMATCH"})
        if canary_claim and canary_claim != CANARY_TENANT:
            blockers.append({"gate": f"{name}.canaryTenant", "reason": "TENANT_MISMATCH"})
    if not visible_positive_resources:
        unverified.append(
            {
                "gate": "crossTenantResourceIsolation",
                "reason": "NO_POSITIVE_RESOURCE_AVAILABLE_FOR_CANARY_COMPARISON",
            }
        )

    return {
        "schemaVersion": 1,
        "collectedAt": datetime.now(timezone.utc).isoformat(),
        "result": (
            "A0_V_REAL_AUTHORIZATION_REVALIDATION_GREEN"
            if not blockers and not unverified
            else "A0_V_BLOCKED_WITH_ACTIONABLE_GAPS"
        ),
        "scope": {
            "positive": {"orgId": POSITIVE_TENANT[0], "projectId": POSITIVE_TENANT[1]},
            "canary": {"orgId": CANARY_TENANT[0], "projectId": CANARY_TENANT[1]},
            "httpMethods": ["GET"],
            "baseUrl": base_url,
            "gitHead": _git_head(repo),
            "databaseEvidenceClass": "HISTORICAL_BACKUP_RECOVERED_THEN_MIGRATED_TO_HEAD",
            "databaseOriginalDataCutoff": "2026-08-05T05:02:48+08:00",
            "runtimeGuards": {
                "migrationMode": "disabled",
                "qyhCron": "disabled",
                "logicAutomation": "disabled",
                "providerHealthMaintenance": "disabled",
                "extensionRuntimeHost": "inactive",
            },
        },
        "summary": {
            "blockerCount": len(blockers),
            "unverifiedCount": len(unverified),
            "blockers": blockers,
            "unverified": unverified,
            "modelCollectionCounts": model_counts,
            "tenantClaims": tenant_claims,
        },
        "observations": {
            "health": health,
            "positive": positive,
            "canary": canary,
            "negative": negatives,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18181")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[3]
    result = collect(args.base_url.rstrip("/"), repo)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "result": result["result"],
                "blockerCount": result["summary"]["blockerCount"],
                "unverifiedCount": result["summary"]["unverifiedCount"],
                "output": str(args.output),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
