"""D1-W4: G6 DLQ handler — 失败时投递 Pipeline DLQ。

executor 失败时投递到 wave_ext._dlq，只存唯一键/错误码/脱敏摘要/时间戳。
不存 PII 明细、输入数据正文、凭据。异常由调用方（ec_live_executor）重新抛出，
本函数不吞异常。
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)

# FR-D1-3: 可重试，DLQ 条目带 retry_count 与 max_retry=3
MAX_RETRY = 3

# PII 脱敏规则：手机号 / 身份证 / 银行卡 / 邮箱 → ***
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"1[3-9]\d{9}"), "***"),       # 手机号
    (re.compile(r"\d{15,18}"), "***"),          # 身份证
    (re.compile(r"62\d{14,17}"), "***"),        # 银行卡号
    (re.compile(r"\S+@\S+\.\S+"), "***"),       # 邮箱
]


def _sanitize_pii(text: str) -> str:
    """脱敏 PII：手机号 / 身份证 / 银行卡 / 邮箱 → ***。"""
    sanitized = text
    for pattern, replacement in _PII_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _summarize_exception(exc: Exception) -> str:
    """生成脱敏的错误摘要：异常类型 + 简短描述（不含完整 traceback）。"""
    raw = f"{type(exc).__name__}: {exc}"
    return _sanitize_pii(raw)


def handle_failure(
    pipeline: Any,
    scope: Any,
    exc: Exception,
) -> None:
    """投递失败 run 到 DLQ。

    - 投递到 wave_ext._dlq，只存唯一键 / 错误码 / 脱敏摘要 / 时间戳
    - 不存 PII 明细、输入数据正文、凭据
    - retry_count=0, max_retry=3
    - 不吞异常（本函数不 raise；ec_live_executor 在调用后自行 raise 传播原异常）

    向后兼容：保留骨架阶段的 log.warning；DLQ 投递本身失败只 log.error，
    不影响原异常传播。
    """
    pipeline_id = getattr(pipeline, "id", "unknown")

    # 骨架行为保留：log warning
    log.warning(
        "ec_pipeline_failed pipeline=%s scope=%s error=%s",
        pipeline_id,
        scope,
        type(exc).__name__,
    )

    # 投递 DLQ（延迟导入避免循环依赖 / router 副作用）
    try:
        from aos_api.routers.wave_ext import _dlq, _resource_key

        dlq_id = f"dlq-{uuid.uuid4().hex[:6]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        summary = _summarize_exception(exc)

        item = {
            "id": dlq_id,
            "pipelineId": pipeline_id,
            "errorCode": type(exc).__name__,
            "reason": summary,
            "status": "open",
            "retry_count": 0,
            "max_retry": MAX_RETRY,
            "createdAt": timestamp,
            "orgId": getattr(scope, "org_id", ""),
            "projectId": getattr(scope, "project_id", ""),
        }
        # 复用 wave_ext 的 scope key 结构：(org_id, project_id, resource_id)
        _dlq[_resource_key(scope, dlq_id)] = item
        log.info(
            "ec_pipeline_dlq_pushed dlq_id=%s pipeline=%s",
            dlq_id,
            pipeline_id,
        )
    except Exception as dlq_exc:
        # DLQ 投递失败不得影响原异常传播（ec_live_executor 仍会 raise 原 exc）
        log.error(
            "ec_pipeline_dlq_push_failed pipeline=%s error=%s",
            pipeline_id,
            type(dlq_exc).__name__,
        )
