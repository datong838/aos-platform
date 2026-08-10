"""AIP 三层运行记忆冷启动 seed.

遵循 06-228-AIP方案 §1 冻结口径：三层运行记忆 (Working / Episodic / Semantic)。
Procedural 不作为运行记忆层——程序性知识以版本化 Wiki 形式灌入（见 okf_wiki_cold_start.py）。

分层灌入策略：
  - **Semantic** (语义记忆): 7 个核心 OT 的领域事实（从 ecom_core_models 派生）。
  - **Episodic** (情景记忆): 1 条系统初始化事件（记录冷启动时间戳）。
  - **Working** (工作记忆): 空——由运行时 TaskRun 按需写入。

幂等：通过固定 id 前缀 + tags 标记，重复执行不重复插入。
"""
from __future__ import annotations

import time

from aos_api.aip_long_memory import MemoryLayer, get_engine
from aos_api.ecom_core_models import REQUIRED_PROPERTIES, DERIVED_PROPERTIES
from aos_api.logging_facade import get_logger

log = get_logger("aos-api.demo.seed_memory_cold_start")

_SEED_TAG = "cold-start-seed"


def _seed_semantic() -> int:
    """灌入语义记忆：每个核心 OT 的必填字段 + 派生指标事实。"""
    eng = get_engine()
    count = 0
    existing_ids = {item.id for item in eng.list_semantic()}

    for ot, required in sorted(REQUIRED_PROPERTIES.items()):
        item_id = f"mem-semantic-{ot.lower()}"
        if item_id in existing_ids:
            continue
        derived = sorted(DERIVED_PROPERTIES.get(ot, frozenset()))
        content = (
            f"# {ot} 领域事实\n\n"
            f"## 必填属性 ({len(required)} 个)\n"
            + "\n".join(f"- `{r}`" for r in sorted(required))
            + "\n\n"
        )
        if derived:
            content += f"## 派生指标 ({len(derived)} 个)\n" + "\n".join(
                f"- `{d}`" for d in derived
            )
        eng.create(
            name=f"{ot} 本体契约",
            config={"object_type": ot, "required_count": len(required)},
            layer=MemoryLayer.SEMANTIC.value,
            content=content,
            object_type=ot,
            tags=[_SEED_TAG, "ontology", ot.lower()],
        )
        count += 1
    return count


def _seed_episodic() -> int:
    """灌入情景记忆：系统初始化事件。"""
    eng = get_engine()
    existing = [item for item in eng.list_episodic() if _SEED_TAG in item.tags]
    if existing:
        return 0

    eng.create(
        name="系统冷启动初始化",
        config={"boot_timestamp": time.time()},
        layer=MemoryLayer.EPISODIC.value,
        content=(
            f"# 系统冷启动\n\n"
            f"- **时间**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())}\n"
            f"- **事件**: AIP 三层运行记忆引擎首次启动\n"
            f"- **动作**: 灌入语义记忆 (12 OT 契约) + 本事件\n"
            f"- **注**: 程序性知识以版本化 Wiki 形式灌入（okf_wiki_cold_start）\n"
        ),
        tags=[_SEED_TAG, "system", "boot"],
    )
    return 1


def seed_memory_cold_start() -> dict[str, int]:
    """执行三层运行记忆冷启动灌入。返回各层灌入计数。"""
    semantic = _seed_semantic()
    episodic = _seed_episodic()
    total = semantic + episodic
    if total:
        log.info(
            "seed_memory_cold_start_done semantic=%s episodic=%s total=%s",
            semantic,
            episodic,
            total,
        )
    return {"semantic": semantic, "episodic": episodic, "total": total}
