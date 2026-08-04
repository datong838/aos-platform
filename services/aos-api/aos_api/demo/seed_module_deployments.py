"""Seed module deployments — Phase 1 Workshop backend.

27 deployment records: 3 environments (dev/staging/prod) × 9 modules.
Idempotent: delete by org_id then insert.
"""
from __future__ import annotations

import json

from aos_api.db import connect
from aos_api.logging_facade import get_logger
from aos_api.module_deployments import ensure_schema
from aos_api.module_identity import stable_module_pk

log = get_logger("aos-api.demo.seed_module_deployments")

_DEFAULT_ORG = "dev-org"
_DEFAULT_PROJECT = "dev-project"

_ENVS = ["dev", "staging", "prod"]
_MODULE_IDS = [
    "dev-module-order",
    "dev-module-risk",
    "dev-module-customer",
    "dev-module-asset",
    "dev-module-analysis",
    "dev-module-workorder",
    "dev-module-inventory",
    "dev-module-finance",
    "dev-module-marketing",
]


def seed_module_deployments() -> int:
    """Idempotently seed 27 deployment records. Returns count."""
    ensure_schema()
    count = 0
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM module_deployment
             WHERE module_id LIKE 'dev-module-%%' AND org_id=%s
            """,
            (_DEFAULT_ORG,),
        )

        for module_id in _MODULE_IDS:
            for i, env in enumerate(_ENVS):
                did = f"dep-{module_id}-{env}"
                version = f"1.0.{i}"
                conn.execute(
                    """
                    INSERT INTO module_deployment (
                        id, module_id, environment, version, status,
                        config_snapshot, deployed_by, org_id, project_id, module_pk
                    ) VALUES (%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                    ON CONFLICT (org_id, project_id, id) DO UPDATE SET
                        version=EXCLUDED.version, status=EXCLUDED.status
                    """,
                    (
                        did,
                        module_id,
                        env,
                        version,
                        "success",
                        json.dumps({"moduleId": module_id, "env": env}),
                        "user:dev",
                        _DEFAULT_ORG,
                        _DEFAULT_PROJECT,
                        stable_module_pk(_DEFAULT_ORG, _DEFAULT_PROJECT, module_id),
                    ),
                )
                count += 1

        conn.commit()
    log.info("seed_module_deployments_done count=%s", count)
    return count
