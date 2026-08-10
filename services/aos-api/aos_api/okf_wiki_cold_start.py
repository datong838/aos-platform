"""OKF Wiki cold-start seed.

When the in-memory WikiEngine is empty (fresh boot, no Phase4 demo seed yet),
this module provides per-OT seed Wiki entries so that AIP-8 (Analyst) and the
Wiki UI never face a "select object + empty gap" dead end.

Each seed Wiki documents the OT's canonical schema (required properties, link
types, derived metrics) in Markdown — the same content that AIP agents consume
for real-data grounding.

Design rules:
  - Pure in-memory: writes to WikiEngine singleton, no DB.
  - Idempotent: skip if a Wiki with the same fixed id already exists.
  - 12 OTs covered: Shop / Product / ProductSku / Category / Order / OrderLine
    / Shipment / CustomerLite / Weapp / SystemConfig / ProductReview / Payment.
  - Fixed ids (``wiki-coldstart-{ot}``) so re-seed is safe.
"""
from __future__ import annotations

from aos_api.ecom_core_models import (
    CORE_LINK_TYPES,
    CORE_OBJECT_TYPES,
    DERIVED_PROPERTIES,
    OPTIONAL_PROPERTIES,
    REQUIRED_PROPERTIES,
)
from aos_api.logging_facade import get_logger
from aos_api.ontology_wiki_engine import get_wiki_engine

log = get_logger("aos-api.okf_wiki_cold_start")


def _ot_links(object_type: str) -> list[str]:
    """Return link type names involving this OT."""
    return [
        lt
        for lt, (src, dst) in CORE_LINK_TYPES.items()
        if src == object_type or dst == object_type
    ]


def _build_content(ot: str) -> str:
    required = sorted(REQUIRED_PROPERTIES.get(ot, frozenset()))
    optional = sorted(OPTIONAL_PROPERTIES.get(ot, frozenset()))
    derived = sorted(DERIVED_PROPERTIES.get(ot, frozenset()))
    links = _ot_links(ot)

    lines: list[str] = [
        f"# {ot} 对象知识手册",
        "",
        f"> 本文由 OKF 冷启动自动生成，描述 **{ot}** 的本体契约。",
        "",
        "## 必填属性 (Required)",
    ]
    for prop in required:
        lines.append(f"- `{prop}`")
    if not required:
        lines.append("- 无")

    lines.append("")
    lines.append("## 可选属性 (Optional)")
    for prop in optional:
        lines.append(f"- `{prop}`")
    if not optional:
        lines.append("- 无")

    lines.append("")
    lines.append("## 派生指标 (Derived)")
    for prop in derived:
        lines.append(f"- `{prop}`")
    if not derived:
        lines.append("- 无")

    lines.append("")
    lines.append("## 关联关系 (Links)")
    for link in links:
        src, dst = CORE_LINK_TYPES[link]
        arrow = "→" if src == ot else "←"
        other = dst if src == ot else src
        lines.append(f"- `{link}` ({arrow} {other})")
    if not links:
        lines.append("- 无")

    lines.append("")
    lines.append("---")
    lines.append(
        "*本内容基于 `ecom_core_models.REQUIRED_PROPERTIES` 自动生成，"
        "可通过 Draft 审批流更新。*"
    )
    return "\n".join(lines)


def seed_okf_wiki_cold_start() -> int:
    """Seed per-OT cold-start Wikis if the engine is empty for that OT.

    Returns the count of newly seeded Wikis.
    """
    eng = get_wiki_engine()
    seeded = 0
    for ot in sorted(CORE_OBJECT_TYPES):
        wiki_id = f"wiki-coldstart-{ot.lower()}"
        if eng.get_wiki(wiki_id) is not None:
            continue
        if eng.find_wiki_by_object_type(ot) is not None:
            continue
        eng.create_wiki(
            id=wiki_id,
            title=f"{ot} 对象知识",
            content=_build_content(ot),
            object_type_id=ot,
            tags=["cold-start", "okf", ot.lower()],
            author="okf-cold-start",
        )
        seeded += 1
    if seeded:
        log.info("seed_okf_wiki_cold_start_done seeded=%s", seeded)
    return seeded
