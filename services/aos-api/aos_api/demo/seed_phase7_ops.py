"""Phase 7 · Ops Delivery 种子数据（43 条）.

Hub 1 + Spokes 5 + Releases 3 + Hotfix 1 + Recall 1 + Ferry bundles 2 + Config/MW/Plan 约 30.
"""
from __future__ import annotations

import time


def seed_ops_data() -> None:
    """Populate OpsDeliveryEngine with seed data."""
    from aos_api.phase7_ops_engine import get_engine

    eng = get_engine()
    eng.reset()
    now = time.time()

    # ── Hub (1) ──
    eng.update_hub(
        version="3.14.0",
        cluster="aos-prod",
        status="healthy",
        region="us-east-1",
        uptime_days=45,
        spokes_count=5,
        metadata={
            "owner": "ops-team",
            "support_tier": "enterprise",
            "k8s_version": "1.28.4",
        },
    )

    # ── Spokes (5) ──
    spoke_specs = [
        ("spoke-prod-useast", "us-east-1", "healthy", "3.14.0", "Production primary cluster"),
        ("spoke-prod-euwest", "eu-west-1", "degraded", "3.14.0", "EU secondary cluster"),
        ("spoke-staging-apac", "ap-southeast-1", "maintenance", "3.14.0-rc2", "APAC staging"),
        ("spoke-dev-local", "us-west-2", "error", "3.13.2", "Development cluster"),
        ("spoke-dr-useast2", "us-east-2", "unreachable", "3.14.0", "DR cluster"),
    ]
    spoke_ids = []
    for name, region, status, ver, desc in spoke_specs:
        s = eng.create_spoke(
            name=name,
            region=region,
            status=status,
            version=ver,
            description=desc,
            url=f"https://{name}.aos.internal",
            config_hash=f"sha256:{name.replace('-', '')[:16]}",
            plan_version="v1" if status == "healthy" else "v2",
            resources={"cpu": 16, "memory_gb": 64, "storage_tb": 2},
            health_checks={
                "api": "ok" if status == "healthy" else "warn",
                "db": "ok" if status != "unreachable" else "fail",
                "storage": "ok",
            },
            tags=[region, status],
        )
        spoke_ids.append(s.id)

    # ── Spoke Configs (5 overrides) ──
    for i, sid in enumerate(spoke_ids):
        overrides = {
            "max_connections": 100 * (i + 1),
            "log_level": "INFO" if i % 2 == 0 else "DEBUG",
            "backup_schedule": f"0 {i*4} * * *",
            "feature_flag_new_ui": i < 3,
        }
        eng.update_spoke_config(sid, overrides=overrides, updated_by=f"admin{i+1}")

    # ── Plan items (6) ──
    for i, sid in enumerate(spoke_ids[:3]):
        actions = ["deploy", "upgrade", "scale"]
        eng.add_plan_item(
            sid,
            action=actions[i],
            resource=f"deployment/aos-core",
            current_state=f"v3.1{i}",
            target_state=f"v3.14",
            status="pending" if i > 0 else "applying",
        )
        # Plan diffs
        eng.add_plan_diff(
            sid,
            path=f"spec.template.spec.containers[0].image",
            current_value=f"aos/core:3.1{i}",
            target_value="aos/core:3.14.0",
            diff_type="modified",
        )
        eng.add_plan_diff(
            sid,
            path=f"spec.replicas",
            current_value=2 + i,
            target_value=4,
            diff_type="modified",
        )

    # ── Maintenance Windows (3) ──
    for i, sid in enumerate(spoke_ids[:3]):
        eng.create_maintenance_window(
            sid,
            start_time=now + 3600 * (i + 1),
            end_time=now + 3600 * (i + 1) + 7200,
            reason=f"Quarterly upgrade cycle {i+1}",
            status="scheduled",
            created_by=f"scheduler{i+1}",
        )

    # ── Releases (3) ──
    eng.create_release(
        channel="stable",
        version="3.14.0",
        released_at=now - 7 * 86400,
        changelog=["Ontology graph v2", "AIP Logic parallel blocks", "Pipeline DAG optimization", "Security patches"],
        commit_hash="abc1234",
        artifacts=["aos-core-3.14.0.tar.gz", "aos-ui-3.14.0.tar.gz"],
        status="published",
    )
    eng.create_release(
        channel="beta",
        version="3.14.1-beta",
        released_at=now - 2 * 86400,
        changelog=["New Model Router UI", "Pipeline scheduling improvements", "Bug fixes"],
        commit_hash="def5678",
        artifacts=["aos-core-3.14.1-beta.tar.gz"],
        status="published",
    )
    eng.create_release(
        channel="rc",
        version="3.15.0-rc1",
        released_at=now - 86400,
        changelog=["Multi-agent orchestration", "Ferry v2 protocol", "New Ops Dashboard"],
        commit_hash="ghi9012",
        artifacts=["aos-core-3.15.0-rc1.tar.gz", "aos-ops-1.0.tar.gz"],
        status="published",
    )

    # ── Hotfix (1) ──
    eng.create_hotfix(
        version="3.14.0-hotfix.1",
        base_version="3.14.0",
        description="Critical security patch for OAuth token refresh",
        created_at=now - 3600,
        status="ready",
        target_spokes=spoke_ids[:2],
    )

    # ── Recall (1) ──
    eng.create_recall(
        from_version="3.13.2",
        to_version="3.13.1",
        reason="Memory leak in Pipeline Builder",
    )

    # ── Ferry Bundles (2) ──
    eng.create_bundle(
        name="ontology-migration-v2",
        version="2.1.0",
        size_mb=256.5,
        artifacts=["ontology-ontology-v2.json", "ontology-types-v2.json"],
        status="ready",
        description="Ontology v2 schema migration bundle",
    )
    eng.create_bundle(
        name="aip-logic-blocks-pack",
        version="1.3.0",
        size_mb=128.0,
        artifacts=["aip-blocks-extended.json", "aip-templates-v3.json"],
        status="ready",
        description="AIP Logic extended block templates",
    )

    # ── Extra config entries (to reach ~43 records) ──
    for sid in spoke_ids[3:]:
        eng.update_spoke_config(sid, overrides={"log_level": "WARN"}, updated_by="system")
        eng.add_plan_item(sid, action="config", resource="configmap/aos-settings", status="applied")
        eng.add_plan_diff(sid, path="data.log_level", current_value="INFO", target_value="WARN", diff_type="modified")

    print(f"[seed_phase7_ops] Seeded: Hub 1 + Spokes {len(spoke_ids)} + Configs {len(eng._spoke_configs)}"
          f" + Plan items {sum(len(v) for v in eng._plan_items.values())}"
          f" + Releases {len(eng._releases)} + Hotfixes {len(eng._hotfixes)}"
          f" + Recalls {len(eng._recalls)} + Bundles {len(eng._ferry_bundles)}")


if __name__ == "__main__":
    seed_ops_data()
