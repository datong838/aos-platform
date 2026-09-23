"""W6-C1: BG-03 product candidate scan for HuangPu-0 sales weapon pack.

Read-only scan over canonical obj_instance (Product) for tenant org-org/dev-project.
Applies 231-9 §2 rules:
  - select 1-3 candidates, with explicit exclusions and unknowns
  - ACTIVE != sellable != profitable (never assert profit/margin as fact)
  - first round picks exactly ONE primary candidate
Output: JSON scan report under replacement-dq/w6-bg03-candidates/.

Usage: .venv/bin/python scripts/a0v_w6_bg03_candidate_scan.py [--section <section>]
Re-run after each new snapshot section (e.g. post 09-24 first dispatch) to refresh.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent / ".aos-recovery-20260920/state/q-advisor-baseline"
STATE = BASE / "replacement-dq/w6-bg03-candidates"

ORG = "org-org"
PROJECT = "dev-project"

# Runtime identity (same as 8080 service; NOINHERIT user -> SET ROLE aos_runtime
# + RLS tenant GUCs required, see W6 session notes 2026-09-23).
DSN = (
    "host=127.0.0.1 port=18435 dbname=aos_meta_head "
    "user=aos_a0v_runtime_20260912 "
    "password=O4E8KenLRUeG2v8hu-O4ms5-71fumMpFMvLvH1ilRpwWJSDz"
)


def _num(props: dict, key: str):
    raw = props.get(key)
    if raw in (None, ""):
        return None
    try:
        return float(raw)
    except (TypeError, ValueError):
        return None


def fetch_products(section: str | None) -> list[dict]:
    where = "AND props->>'observedAt' LIKE %s" if section else ""
    params = ("Product", ORG, PROJECT) + ((section + "%",) if section else ())
    sql = f"""
        SELECT object_id, props FROM obj_instance
        WHERE object_type=%s AND org_id=%s AND project_id=%s {where}
    """
    with psycopg.connect(DSN) as conn:
        conn.execute("SET ROLE aos_runtime")
        conn.execute("SELECT set_config('aos.org_id', %s, false)", (ORG,))
        conn.execute("SELECT set_config('aos.project_id', %s, false)", (PROJECT,))
        rows = conn.execute(sql, params).fetchall()
    out = []
    for oid, props in rows:
        out.append({
            "object_id": oid,
            "title": props.get("title"),
            "status": props.get("status"),
            "price": _num(props, "price"),
            "cost_price": _num(props, "costPrice"),
            "market_price": _num(props, "marketPrice"),
            "stock": _num(props, "stock"),
            "sale_num": _num(props, "saleNum"),
            "brand": props.get("brandName") or None,
            "category_ids": props.get("categoryId"),
            "is_free_shipping": props.get("isFreeShipping"),
            "is_virtual": props.get("isVirtual"),
            "observed_at": props.get("observedAt"),
            "content_len": len(props.get("content") or ""),
            "introduction_len": len(props.get("introduction") or ""),
            "image_count": len([i for i in (props.get("image") or "").split(",") if i]),
        })
    return out


def classify(products: list[dict]) -> dict:
    excluded: list[dict] = []
    pool: list[dict] = []

    for p in products:
        reasons = []
        if p["status"] != "ACTIVE":
            reasons.append(f"status={p['status']}")
        if p.get("is_virtual") == 1:
            reasons.append("virtual goods")
        if (p["stock"] or 0) <= 0:
            reasons.append("no stock")
        elif (p["stock"] or 0) < 10:
            reasons.append(f"low stock ({p['stock']:.0f})")
        if reasons:
            excluded.append({"object_id": p["object_id"], "title": p["title"],
                             "reasons": reasons, "bucket": "hard"})
            continue

        title = p["title"] or ""
        # Policy exclusions per 231-9 (membership/distribution rights packs, big
        # promise bundles) — these are not eligible for a first sales weapon pack.
        if any(k in title for k in ("会员", "合伙人", "星推", "创业晋级", "钜惠包")):
            excluded.append({"object_id": p["object_id"], "title": title,
                             "reasons": ["membership/distribution rights goods (compliance risk)"],
                             "bucket": "policy"})
            continue
        if p["price"] and p["price"] >= 300:
            excluded.append({"object_id": p["object_id"], "title": title,
                             "reasons": [f"high price {p['price']:.0f} not fit first pack"],
                             "bucket": "policy"})
            continue
        if (p["sale_num"] or 0) < 3:
            excluded.append({"object_id": p["object_id"], "title": title,
                             "reasons": [f"insufficient sales evidence ({(p['sale_num'] or 0):.0f})"],
                             "bucket": "evidence"})
            continue
        pool.append(p)

    # Rank remaining pool: sales evidence first, then stock depth, then price band.
    def score(p):
        sales = p["sale_num"] or 0
        stock = min(p["stock"] or 0, 200)
        price_fit = 1 if (p["price"] and 10 <= p["price"] <= 60) else 0
        content_fit = 1 if p["introduction_len"] > 20 and p["image_count"] >= 1 else 0
        return (sales, stock / 100, price_fit, content_fit)

    pool.sort(key=score, reverse=True)
    candidates = []
    for rank, p in enumerate(pool[:3], start=1):
        candidates.append({
            "rank": rank,
            "object_id": p["object_id"],
            "title": p["title"],
            "brand": p["brand"],
            "price": p["price"],
            "stock": p["stock"],
            "sale_num": p["sale_num"],
            "why": (
                f"sales={p['sale_num']:.0f}, stock={p['stock']:.0f}, "
                f"price={p['price']:.2f}, intro_len={p['introduction_len']}, "
                f"images={p['image_count']}"
            ),
            "unknowns": [
                "true margin unknown (costPrice excludes platform fee/logistics/after-sales/promotion)",
                "channel-side listing status unverified (ACTIVE+stock is necessary, not sufficient)",
                "audience fit hypothesis unverified (needs HuangPu-0 cohort assumption)",
            ],
        })

    primary = None
    if candidates:
        primary = {
            "object_id": candidates[0]["object_id"],
            "title": candidates[0]["title"],
            "rationale": (
                "highest sales evidence with adequate stock and accessible price band; "
                "single primary per 231-9 §2 (first round picks exactly one)"
            ),
        }

    return {
        "candidates": candidates,
        "primary": primary,
        "excluded": excluded,
        "unknowns_global": [
            "margin/profit NOT asserted anywhere in this scan (cost data present but incomplete)",
            "seasonal fit not judged (e.g. SPF products in autumn = unknown)",
            "no cohort/audience data joined yet (CustomerLite analysis is W6-C2/W7 scope)",
            "data section is the latest canonical snapshot; re-scan after next dispatch",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--section", default=None, help="observedAt prefix e.g. 2026-09-24")
    args = parser.parse_args()

    products = fetch_products(args.section)
    if not products:
        print(f"no Product rows found (section={args.section!r})")
        return 1

    report = {
        "scannedAt": datetime.now(timezone.utc).isoformat(),
        "section": args.section or "latest",
        "tenant": {"org_id": ORG, "project_id": PROJECT},
        "total_products": len(products),
        "status_dist": {},
        **classify(products),
    }
    for p in products:
        report["status_dist"][p["status"]] = report["status_dist"].get(p["status"], 0) + 1

    STATE.mkdir(parents=True, exist_ok=True)
    section_tag = (args.section or "latest").replace(":", "").replace("-", "")
    out_path = STATE / f"candidate-scan-{section_tag}.json"
    out_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    os.chmod(out_path, 0o600)

    print(f"total={report['total_products']} status={report['status_dist']}")
    print(f"candidates={len(report['candidates'])} excluded={len(report['excluded'])}")
    for c in report["candidates"]:
        print(f"  #{c['rank']} {c['object_id']} {c['title']} — {c['why']}")
    if report["primary"]:
        print(f"PRIMARY: {report['primary']['object_id']} {report['primary']['title']}")
    print(f"report: {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
