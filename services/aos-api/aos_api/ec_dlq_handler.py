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

# PII 脱敏规则：身份证 / 银行卡 / 手机号 / 邮箱 → ***
# 顺序：长 pattern 先匹配，避免短 pattern（手机号）部分匹配 18 位身份证中的 11 位子串
# 手机号支持带分隔符格式：138-0000-0000、138 0000 0000、13800000000
_PII_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\d{15,18}"), "***"),          # 身份证（先长 pattern）
    (re.compile(r"62\d{14,17}"), "***"),        # 银行卡号
    (re.compile(r"1[3-9]\d[\s-]?\d{4}[\s-]?\d{4}"), "***"),  # 手机号（含分隔符）
    (re.compile(r"\S+@\S+\.\S+"), "***"),       # 邮箱
    (re.compile(r"openid[_\w-]+", re.IGNORECASE), "***"),  # openid
]


def _sanitize_pii(text: str) -> str:
    """脱敏 PII：手机号 / 身份证 / 银行卡 / 邮箱 → ***。"""
    sanitized = text
    for pattern, replacement in _PII_PATTERNS:
        sanitized = pattern.sub(replacement, sanitized)
    return sanitized


def _sanitize_recursive(obj: Any) -> Any:
    """O1-A G18: 递归脱敏 — 深度遍历 dict/list/str，对所有字符串做 PII 脱敏。

    - str → _sanitize_pii
    - dict → 对每个 value 递归
    - list/tuple → 对每个元素递归
    - 其他类型 → 原样返回
    """
    if isinstance(obj, str):
        return _sanitize_pii(obj)
    if isinstance(obj, dict):
        return {k: _sanitize_recursive(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return type(obj)(_sanitize_recursive(item) for item in obj)
    return obj


def classify_pipeline_error(exc: Exception) -> str:
    """O1-A G18: 错误分类 — 先检查 EcomConsistencyError.code，否则用异常类名。

    返回值用于 DLQ 的 errorCode 字段，确保领域错误有语义化的错误码。
    """
    # 检查 EcomConsistencyError（领域错误）
    code = getattr(exc, "code", None)
    if code and isinstance(code, str):
        return code
    # 检查 __cause__ 链中的 EcomConsistencyError
    cause = getattr(exc, "__cause__", None)
    while cause is not None:
        cause_code = getattr(cause, "code", None)
        if cause_code and isinstance(cause_code, str):
            return cause_code
        cause = getattr(cause, "__cause__", None)
    # 回退到异常类名
    return type(exc).__name__


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
            "errorCode": classify_pipeline_error(exc),
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
