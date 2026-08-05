"""D1-W3: G5 OTWriter — executor 输出落地到 ecom_object + ecom_link。

骨架阶段：空实现（返回零计数），不落地 OT。
Worker W3 实现：调用 ecom_consistency_store.batch_upsert（单事务 upsert→link→checkpoint→receipt）。
"""

from __future__ import annotations

from typing import Any


def sink_to_ot(
    eng: Any,
    scope: Any,
    pipeline: Any,
    output_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """将输出行落地为 OT + Link。

    骨架：空实现（返回零计数，不落地 OT）。
    W3 实现后：调用 ecom_consistency_store.batch_upsert。
    """
    return {"objects_written": 0, "links_written": 0}
