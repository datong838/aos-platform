"""D1-W4: G6 DLQ handler — 失败时投递 Pipeline DLQ。

骨架阶段：只 log 异常（不投递 DLQ）。
Worker W4 实现：投递到 wave_ext._dlq，只存键/错误码/脱敏摘要。
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)


def handle_failure(
    pipeline: Any,
    scope: Any,
    exc: Exception,
) -> None:
    """投递失败 run 到 DLQ。

    骨架：只 log 异常（不投递 DLQ）。
    W4 实现后：投递到 wave_ext._dlq，只存唯一键/错误码/脱敏摘要/时间戳。
    """
    log.warning(
        "ec_pipeline_failed pipeline=%s scope=%s error=%s",
        getattr(pipeline, "id", "?"),
        scope,
        type(exc).__name__,
    )
