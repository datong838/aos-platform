"""D1-W4: G6 DLQ handler 测试（FR-D1-3）。

测试约束：
- handle_failure 将失败信息投递到 DLQ（不是只 log）
- DLQ 条目包含：唯一键、错误码、脱敏摘要、时间戳
- DLQ 条目不包含 PII 明细、输入数据正文、凭据
- DLQ 条目包含 retry_count=0 和 max_retry=3
- 异常被重新抛出（raise），不吞掉异常
- 骨架行为（log.warning）仍然工作（向后兼容）
"""

from __future__ import annotations

import logging

import pytest

from aos_api.ec_dlq_handler import handle_failure
from aos_api.logging_facade import configure_logging
from aos_api.routers.wave_ext import _dlq
from aos_api.tenant_scope import TenantScope

# 预先完成 logging 配置：configure_logging() 会 root.handlers.clear()，
# 若推迟到测试中执行会清掉 pytest caplog 注入的 handler 导致捕获失败。
configure_logging()

TEST_SCOPE = TenantScope("dev-org", "dev-project")


@pytest.fixture(autouse=True)
def reset_dlq():
    """每个测试前后清空 wave_ext._dlq，避免相互污染。"""
    _dlq.clear()
    yield
    _dlq.clear()


class _FakePipeline:
    """轻量 pipeline 替身，只暴露 id。"""

    def __init__(self, pid: str = "pipe-1"):
        self.id = pid


# ── RED: 以下测试在骨架阶段应全部失败（骨架只 log，不投递 DLQ） ──


def test_handle_failure_pushes_to_dlq():
    """handle_failure 将失败信息投递到 DLQ，不是只 log。"""
    exc = RuntimeError("boom")
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    assert len(_dlq) == 1, "DLQ 应有 1 条记录（骨架阶段为 0）"


def test_dlq_entry_contains_key_fields():
    """DLQ 条目包含：唯一键、错误码、脱敏摘要、时间戳。"""
    handle_failure(_FakePipeline("pipe-1"), TEST_SCOPE, RuntimeError("boom"))

    [item] = list(_dlq.values())
    # 唯一键
    assert "id" in item and item["id"].startswith("dlq-")
    # 关联 pipeline
    assert item["pipelineId"] == "pipe-1"
    # 错误码（异常类型名）
    assert item["errorCode"] == "RuntimeError"
    # 脱敏摘要
    assert "boom" in item["reason"]
    # 时间戳
    assert "createdAt" in item and item["createdAt"]
    # scope 隔离字段
    assert item["orgId"] == "dev-org"
    assert item["projectId"] == "dev-project"


def test_dlq_entry_does_not_contain_pii():
    """DLQ 条目不含 PII 明细（手机号必须脱敏）。"""
    exc = RuntimeError("user phone 13800138000 failed")
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    [item] = list(_dlq.values())
    assert "13800138000" not in item["reason"], "手机号必须脱敏为 ***"
    assert "***" in item["reason"]


def test_dlq_entry_does_not_contain_input_data_or_credentials():
    """DLQ 条目不存输入数据正文、凭据。"""
    handle_failure(_FakePipeline(), TEST_SCOPE, RuntimeError("auth failed"))

    [item] = list(_dlq.values())
    # 不应出现输入正文 / 凭据相关字段
    for forbidden in ("input", "input_data", "payload", "credentials", "body", "sample_input"):
        assert forbidden not in item, f"DLQ 条目不应包含 {forbidden}"


def test_dlq_entry_has_retry_count_and_max_retry():
    """DLQ 条目带 retry_count=0 与 max_retry=3（可重试）。"""
    handle_failure(_FakePipeline(), TEST_SCOPE, RuntimeError("boom"))

    [item] = list(_dlq.values())
    assert item["retry_count"] == 0
    assert item["max_retry"] == 3


def test_handle_failure_does_not_swallow_exception():
    """handle_failure 不吞异常：调用后原异常对象仍可被外层 raise。

    ec_live_executor 在 handle_failure 之后 raise，本函数若吞异常会破坏该契约。
    """
    original_exc = RuntimeError("original failure")

    try:
        raise original_exc
    except Exception as exc:
        handle_failure(_FakePipeline(), TEST_SCOPE, exc)
        # handle_failure 正常返回，不抛新异常，原异常对象保持不变
        assert exc is original_exc


class _ListHandler(logging.Handler):
    """捕获日志记录到列表，用于验证 log 行为（不依赖 caplog 传播）。"""

    def __init__(self) -> None:
        super().__init__(level=logging.WARNING)
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def test_handle_failure_still_logs_warning_for_backward_compat():
    """骨架行为（log.warning ec_pipeline_failed）仍然工作（向后兼容）。"""
    logger = logging.getLogger("aos_api.ec_dlq_handler")
    # 某些 pytest 插件 / 全局 logging 配置可能把 logger.disabled 置为 True，
    # 这里显式恢复，确保能验证 log.warning 行为。
    logger.disabled = False
    handler = _ListHandler()
    logger.addHandler(handler)
    try:
        handle_failure(_FakePipeline("pipe-x"), TEST_SCOPE, RuntimeError("boom"))
    finally:
        logger.removeHandler(handler)

    messages = [r.getMessage() for r in handler.records]
    assert any(
        "ec_pipeline_failed" in m and "pipe-x" in m for m in messages
    ), f"应保留骨架的 log.warning 行为，实际 records={messages}"


def test_dlq_entry_sanitizes_multiple_pii_types():
    """PII 脱敏覆盖手机号 / 身份证 / 银行卡 / 邮箱。"""
    exc = RuntimeError(
        "contact 13800138000 id 110101199003071234 card 6222020200112345 email a@b.com"
    )
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    [item] = list(_dlq.values())
    reason = item["reason"]
    assert "13800138000" not in reason, "手机号未脱敏"
    assert "110101199003071234" not in reason, "身份证未脱敏"
    assert "6222020200112345" not in reason, "银行卡未脱敏"
    assert "a@b.com" not in reason, "邮箱未脱敏"


def test_ec_live_executor_raises_and_pushes_dlq_on_failure(monkeypatch):
    """集成：ec_live_executor 失败时，异常被重新抛出且 DLQ 被投递。

    验证 FR-D1-3：executor 失败 → 自动入 DLQ + 异常传播（run status 由
    phase5_pipeline_engine 据此置 failed）。
    """
    from aos_api import ec_live_executor as mod

    def _boom(**_kwargs):
        raise RuntimeError("source fetch failed")

    # 让 source 步骤抛异常，触发 except 分支
    monkeypatch.setattr(mod, "fetch_source_rows", _boom)

    with pytest.raises(RuntimeError, match="source fetch failed"):
        mod.ec_live_executor(
            pipeline=_FakePipeline("pipe-ec"),
            nodes=[],
            node_id=None,
            sample_input={},
            execution_kind="schedule",
            cancel_event=None,
            deadline=0,
            scope=TEST_SCOPE,
        )

    # 异常被 raise 的同时，DLQ 也被投递
    assert len(_dlq) == 1
    [item] = list(_dlq.values())
    assert item["pipelineId"] == "pipe-ec"
    assert item["errorCode"] == "RuntimeError"
    assert "source fetch failed" in item["reason"]
