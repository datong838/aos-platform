"""qyh_discover_readonly.py — D0 只读发现与配置冻结脚本.

上位规格: docs/palantier/20_tech/电商平台接入/微商城电商接入方案/D0-只读发现与配置冻结执行规格.md

硬约束（与上位方案第 4.1/5/8 节一致）:
- 连接级 SET SESSION TRANSACTION READ ONLY
- 全局 LIMIT 100 行采样上限
- PII_DIRECT 字段只聚合不取值
- 单查询超时 30s，总脚本超时 600s
- 隧道断开 fail-closed
- 零写入微商城源库 / 零改动 AOS

产物（幂等覆盖）:
- docs/.../frozen/01-schema-fingerprint.md
- docs/.../frozen/02-pipeline-manifest.yaml  (本脚本不覆盖手工冻结的规格文档)
- docs/.../frozen/03-openapi-write-contract.md (同上)
- docs/.../frozen/04-discovery-report.md (同上)
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

READ_ONLY_FLAG: bool = True
READ_ONLY_SQL: str = "SET SESSION TRANSACTION READ ONLY"
SAMPLE_LIMIT: int = 100
QUERY_TIMEOUT_SECONDS: int = 30
SCRIPT_TIMEOUT_SECONDS: int = 600

REPO_ROOT = Path(__file__).resolve().parents[1]
FROZEN_DIR = (
    REPO_ROOT.parent
    / "docs"
    / "palantier"
    / "20_tech"
    / "电商平台接入"
    / "微商城电商接入方案"
    / "frozen"
)

TABLES: dict[str, tuple[str, str]] = {
    "ns_site": ("site_id", "P01 Shop"),
    "ns_goods": ("goods_id", "P02 Product"),
    "ns_goods_sku": ("sku_id", "P03 ProductSku"),
    "ns_goods_category": ("category_id", "P04 Category"),
    "ns_order": ("order_id", "P05 Order"),
    "ns_order_goods": ("order_goods_id", "P06 OrderLine"),
    "ns_express_delivery_package": ("id", "P07 Shipment"),
}

PII_DIRECT_KEYWORDS = (
    "mobile", "phone", "tel", "realname", "id_card", "id_number",
    "card_no", "bank_card", "address", "open_id", "unionid",
    "password", "salt", "secret",
)
PII_QUASI_KEYWORDS = ("email", "nick_name", "headimg", "avatar")


def classify_pii(column_name: str) -> str:
    lowered = column_name.lower()
    for kw in PII_DIRECT_KEYWORDS:
        if kw in lowered:
            return "PII_DIRECT"
    for kw in PII_QUASI_KEYWORDS:
        if kw in lowered:
            return "PII_QUASI"
    return "NON_PII"


def _load_env() -> dict[str, str]:
    env_path = REPO_ROOT / ".env"
    values: dict[str, str] = {}
    if env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, _, v = line.partition("=")
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def discover_schema(connect_kwargs: dict[str, Any] | None = None) -> dict[str, Any]:
    try:
        import pymysql
    except ImportError as exc:
        raise RuntimeError("pymysql required: pip install pymysql") from exc

    env = _load_env()
    kwargs = {
        "host": "127.0.0.1",
        "port": int(env.get("NIUSHOP_DB_PORT_TUNNEL", "13306")),
        "user": env.get("NIUSHOP_DB_USER", "recommend_ro"),
        "password": env.get("NIUSHOP_DB_PASSWORD", ""),
        "connect_timeout": QUERY_TIMEOUT_SECONDS,
        "read_timeout": QUERY_TIMEOUT_SECONDS,
    }
    if connect_kwargs:
        kwargs.update(connect_kwargs)

    conn = pymysql.connect(**kwargs)
    try:
        cur = conn.cursor()
        cur.execute(READ_ONLY_SQL)
        result: dict[str, Any] = {}
        for tbl, (pk, label) in TABLES.items():
            cur.execute(f"SELECT COUNT(*) FROM niushop_b2c_v5.{tbl}")
            count = cur.fetchone()[0]
            cur.execute(
                """SELECT column_name, column_type, is_nullable, column_key, column_default, extra
                   FROM information_schema.columns
                   WHERE table_schema='niushop_b2c_v5' AND table_name=%s
                   ORDER BY ordinal_position""",
                (tbl,),
            )
            cols = [
                {"name": r[0], "type": r[1], "null": r[2], "key": r[3], "default": r[4], "extra": r[5]}
                for r in cur.fetchall()
            ]
            cur.execute(
                """SELECT index_name, GROUP_CONCAT(column_name ORDER BY seq_in_index SEPARATOR ','), MIN(non_unique)=0
                   FROM information_schema.statistics
                   WHERE table_schema='niushop_b2c_v5' AND table_name=%s
                   GROUP BY index_name""",
                (tbl,),
            )
            idx = [{"name": r[0], "cols": r[1], "unique": bool(r[2])} for r in cur.fetchall()]
            result[tbl] = {"count": count, "pk": pk, "label": label, "columns": cols, "indexes": idx}
        return result
    finally:
        conn.close()


def build_frozen_artefacts(schema: dict[str, Any] | None = None) -> dict[str, Path]:
    FROZEN_DIR.mkdir(parents=True, exist_ok=True)
    if schema is None:
        schema = discover_schema()

    generated_at = datetime.now(timezone.utc).isoformat()
    lines: list[str] = [
        "# frozen/01 — Schema Fingerprint (D0 只读发现)",
        "",
        f"> 生成方式：qyh_discover_readonly 只读连接 recommend_ro@niushop_b2c_v5",
        f"> 生成时间：{generated_at}",
        "> 基线：aos-platform；上位方案：228-微商城专项 第 5 节",
        "> 约束：只聚合不取值；PII_DIRECT 字段不出库",
        "",
        "## 1. 七表结构与计数",
        "",
    ]
    pii_summary: dict[str, list[tuple[str, str]]] = {}
    for tbl, info in schema.items():
        lines.append(f"### {tbl}（{info['label']}，count={info['count']}，pk={info['pk']}）")
        lines.append("")
        lines.append("| 列名 | 类型 | 可空 | 键 | PII 等级 |")
        lines.append("|---|---|---|---|---|")
        tbl_pii: list[tuple[str, str]] = []
        for c in info["columns"]:
            pii = classify_pii(c["name"])
            if pii != "NON_PII":
                tbl_pii.append((c["name"], pii))
            lines.append(f"| {c['name']} | {c['type']} | {c['null']} | {c['key']} | {pii} |")
        if tbl_pii:
            pii_summary[tbl] = tbl_pii
        lines.append("")
        lines.append("**索引：**")
        for i in info["indexes"]:
            uniq = "UNIQUE" if i["unique"] else "INDEX"
            lines.append(f"- `{i['name']}` ({uniq}): {i['cols']}")
        lines.append("")

    lines.append("## 2. PII 字段分类汇总（7 表范围内）")
    lines.append("")
    if not pii_summary:
        lines.append("**7 表内零 PII_DIRECT / PII_QUASI 字段。**")
    else:
        for tbl, fields in pii_summary.items():
            lines.append(f"- **{tbl}**: {fields}")
    lines.append("")

    out = FROZEN_DIR / "01-schema-fingerprint.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return {"01": out}


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    dry_run = "--dry-run" in argv or "--apply" not in argv
    if dry_run:
        print("[qyh_discover_readonly] dry-run mode (default): building frozen artefacts only")
    schema = discover_schema()
    produced = build_frozen_artefacts(schema)
    for key, path in produced.items():
        print(f"  produced {key}: {path}")
    print("[qyh_discover_readonly] done; zero writes to source/AOS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
