#!/usr/bin/env python3
"""
O1-A0 §4.1.4: 别名只读盘点门

为 org-org/dev-project 的现有 obj_instance 生成版本化 manifest：
- 旧复合主键
- 目标 Canonical ID
- ObjectType
- props hash
- 来源推断
- 冲突类别和处置状态

只读事务，不更新实例。
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import paramiko


# ── Pipeline-prefixed → Canonical OT mapping ──
ALIAS_TO_CANONICAL: dict[str, str] = {
    "P02-product-qyh": "Product",
    "P03-product-sku-qyh": "ProductSku",
    "P07-shipment-qyh": "Shipment",
    "P08-customer-lite-qyh": "CustomerLite",
    "P09-weapp-qyh": "Weapp",
    "P10-system-config-qyh": "SystemConfig",
    "P11-product-review-qyh": "ProductReview",
    "P12-payment-qyh": "Payment",
}


def _run_psql(sql: str) -> str:
    """通过 docker exec 执行 PSQL，返回结果。"""
    result = subprocess.run(
        ["docker", "exec", "aos-dev-pg", "psql", "-U", "aos_app", "-d", "aos_meta",
         "-t", "-A", "-F", "\t", "-c", sql],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"PSQL failed: {result.stderr}")
    return result.stdout.strip()


def main() -> int:
    start_time = datetime.now(timezone.utc)

    print("→ O1-A0 别名只读盘点")
    print(f"  org=org-org, project=dev-project")

    # 1. 查询所有别名行（pipeline-prefixed object_type）
    print("→ 查询别名行...")

    alias_sql = """
    SELECT
      org_id || '|' || project_id || '|' || object_type || '|' || object_id AS old_pk,
      object_id AS external_id,
      object_type AS old_object_type,
      project_id,
      md5(props::text) AS props_hash,
      '' AS platform,
      '' AS shop_or_marketplace_id
    FROM obj_instance
    WHERE org_id = 'org-org' AND project_id = 'dev-project'
      AND object_type LIKE 'P%-%'
    ORDER BY object_type, object_id;
    """

    raw = _run_psql(alias_sql)
    if not raw:
        print("✗ 未找到别名行")
        return 1

    rows: list[dict] = []
    for line in raw.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 6:
            continue
        old_ot = parts[2]
        canonical_ot = ALIAS_TO_CANONICAL.get(old_ot, "UNKNOWN")
        rows.append({
            "old_pk": parts[0],
            "external_id": parts[1],
            "old_object_type": old_ot,
            "canonical_object_type": canonical_ot,
            "project_id": parts[3],
            "props_hash": parts[4],
            "platform": parts[5],
            "shop_or_marketplace_id": parts[6] if len(parts) > 6 else "",
            "target_canonical_id": parts[5] + ":" + canonical_ot + ":" + parts[1] if len(parts) > 5 else canonical_ot + ":" + parts[1],
            "conflict_category": None,
            "disposition": "pending",
        })

    print(f"  ✓ {len(rows)} 条别名候选")

    # 2. 检查是否有对应的 canonical OT 行（冲突检测）
    print("→ 检查冲突...")

    canonical_sql = f"""
    SELECT object_type, object_id, COUNT(*) AS cnt
    FROM obj_instance
    WHERE org_id = 'org-org' AND project_id = 'dev-project'
      AND object_type IN ({','.join(f"'{v}'" for v in ALIAS_TO_CANONICAL.values())})
    GROUP BY object_type, object_id;
    """
    canon_raw = _run_psql(canonical_sql)
    canonical_map: set[str,] = set()
    for line in canon_raw.split("\n"):
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            canonical_map.add(parts[0] + "|" + parts[1])

    for row in rows:
        canon_key = row["canonical_object_type"] + "|" + row["external_id"]
        if canon_key in canonical_map:
            row["conflict_category"] = "duplicate_canonical_exists"
        else:
            row["conflict_category"] = "no_conflict"

    conflicts = sum(1 for r in rows if r["conflict_category"] != "no_conflict")
    no_conflicts = sum(1 for r in rows if r["conflict_category"] == "no_conflict")
    print(f"  ✓ 无冲突: {no_conflicts}, 有冲突: {conflicts}")

    # 3. 按 OT 分组统计
    by_ot: dict[str, int] = {}
    for r in rows:
        by_ot[r["old_object_type"]] = by_ot.get(r["old_object_type"], 0) + 1

    # 4. 生成 manifest
    # SQL hash（用于证据完整性验证）
    sql_hash = hashlib.sha256(alias_sql.encode()).hexdigest()
    manifest_sql_hash = hashlib.sha256(
        json.dumps(rows, sort_keys=True).encode()
    ).hexdigest()

    # 获取 git 信息
    git_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True, text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    ).stdout.strip()

    # 获取 doc 版本
    doc_path = Path(__file__).resolve().parents[3] / "docs" / "palantier" / "20_tech" / "电商平台接入" / "微商城电商接入方案" / "D-waves" / "O1-本体数字孪生层改造方案.md"
    doc_sha = hashlib.sha256(doc_path.read_bytes()).hexdigest()[:16] if doc_path.exists() else "FILE_NOT_FOUND"

    manifest: dict = {
        "gate": "O1-A0-alias-inventory",
        "generated_at": start_time.isoformat(),
        "org_id": "org-org",
        "project_id": "dev-project",
        "git_sha": git_sha,
        "doc_sha256_prefix": doc_sha,
        "sql_hash": sql_hash,
        "total_alias_rows": len(rows),
        "by_object_type": by_ot,
        "conflicts": {
            "no_conflict": no_conflicts,
            "duplicate_canonical_exists": conflicts,
        },
        "manifest_data_hash": manifest_sql_hash,
        "rows": rows,
    }

    # 5. 写入证据文件
    evidence_dir = Path(__file__).resolve().parents[1] / "tests" / "d5e" / "evidence"
    evidence_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    evidence_file = evidence_dir / f"O1-A0_alias_manifest_{timestamp}.json"
    evidence_file.write_text(json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")

    print(f"\n📄 Manifest: {evidence_file}")
    print(f"\n统计:")
    print(f"  总别名行: {len(rows)}")
    print(f"  按 OT:")
    for ot, cnt in sorted(by_ot.items()):
        print(f"    {ot}: {cnt}")
    print(f"  冲突: {conflicts}, 无冲突: {no_conflicts}")
    print(f"  manifest hash: {manifest_sql_hash[:16]}...")

    return 0


if __name__ == "__main__":
    sys.exit(main())
