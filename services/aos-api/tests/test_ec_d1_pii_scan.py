"""D1-W2: PII 扫描测试 (FR-D1-3 / NFR: PII 明细泄漏 = 0).

验证 ec_dlq_handler 的 PII 脱敏能力，确保 DLQ 条目不含 PII 明文：
- 直接测试 _sanitize_pii 对手机号 / 身份证 / 银行卡 / 邮箱 的脱敏效果
- 扫描 handle_failure 产出的 DLQ 条目，正则匹配 PII pattern
- 验证 DLQ 条目只存：唯一键、错误码、脱敏摘要、时间戳
- 覆盖边界：空字符串、无 PII、混合 PII、连续 PII、长数字串
"""

from __future__ import annotations

import re

import pytest

from aos_api.ec_dlq_handler import _sanitize_pii, handle_failure
from aos_api.logging_facade import configure_logging
from aos_api.routers.wave_ext import _dlq
from aos_api.tenant_scope import TenantScope

# 预先完成 logging 配置：configure_logging() 会 root.handlers.clear()，
# 若推迟到测试中执行会清掉 pytest caplog 注入的 handler 导致捕获失败。
configure_logging()

TEST_SCOPE = TenantScope("dev-org", "dev-project")

# PII 正则（与 ec_dlq_handler._PII_PATTERNS 一致，用于扫描 DLQ 条目）
_PII_REGEXES = [
    re.compile(r"1[3-9]\d{9}"),       # 手机号
    re.compile(r"\d{15,18}"),          # 身份证
    re.compile(r"62\d{14,17}"),        # 银行卡号
    re.compile(r"\S+@\S+\.\S+"),       # 邮箱
]


@pytest.fixture(autouse=True)
def reset_dlq():
    """每个测试前后清空 wave_ext._dlq，避免相互污染。"""
    _dlq.clear()
    yield
    _dlq.clear()


class _FakePipeline:
    """轻量 pipeline 替身，只暴露 id。"""

    def __init__(self, pid: str = "pipe-pii") -> None:
        self.id = pid


# ── 1. _sanitize_pii 单元测试 ──


def test_sanitize_phone_number() -> None:
    """手机号脱敏为 ***。"""
    assert _sanitize_pii("contact 13800138000") == "contact ***"
    assert _sanitize_pii("13800138000") == "***"


def test_sanitize_id_card() -> None:
    """身份证（18 位，不含 1[3-9] 子串）脱敏为 ***。

    选 2000 年出生的身份证（110101200003071234），避免 19xx 年份中的
    `19` 被手机号正则 `1[3-9]\\d{9}` 先部分匹配（Phase A 实际行为）。
    """
    assert _sanitize_pii("id 110101200003071234") == "id ***"


def test_sanitize_id_card_19xx_year_partial_masked() -> None:
    """19xx 年身份证含 `19` 子串 → 手机号正则先部分匹配，完整号码仍不出现。

    Phase A 的 _PII_PATTERNS 顺序：手机号 → 身份证 → 银行卡 → 邮箱。
    `110101199003071234` 中 `19900307123` 满足 `1[3-9]\\d{9}` 被先脱敏为 ***，
    剩余 `110101***4` 不再满足 `\\d{15,18}`。完整身份证号不出现 → 安全。
    """
    result = _sanitize_pii("id 110101199003071234")
    assert "110101199003071234" not in result  # 完整号码不出现
    assert "***" in result  # 有脱敏标记


def test_sanitize_bank_card() -> None:
    """银行卡号脱敏为 ***。"""
    # 16 位银行卡（62 开头）
    result = _sanitize_pii("card 6222020200112345")
    assert "6222020200112345" not in result
    assert "***" in result


def test_sanitize_email() -> None:
    """邮箱脱敏为 ***。"""
    assert _sanitize_pii("mail a@b.com") == "mail ***"
    assert _sanitize_pii("user.name@example.org") == "***"


def test_sanitize_empty_string() -> None:
    """空字符串不变。"""
    assert _sanitize_pii("") == ""


def test_sanitize_no_pii() -> None:
    """无 PII 的字符串不变。"""
    text = "pipeline failed with code RUNTIME_ERROR"
    assert _sanitize_pii(text) == text


def test_sanitize_mixed_pii() -> None:
    """混合 PII 全部脱敏。"""
    text = "user 13800138000 id 110101199003071234 mail a@b.com"
    result = _sanitize_pii(text)
    assert "13800138000" not in result
    assert "110101199003071234" not in result
    assert "a@b.com" not in result
    assert "***" in result


def test_sanitize_multiple_phones() -> None:
    """连续多个手机号全部脱敏。"""
    text = "13800138000 and 13900139000"
    result = _sanitize_pii(text)
    assert "13800138000" not in result
    assert "13900139000" not in result


def test_sanitize_preserves_non_pii_digits() -> None:
    """短数字（非 PII）保留不变。"""
    text = "error code 42 at line 100"
    assert _sanitize_pii(text) == text


# ── 2. DLQ 条目 PII 扫描 ──


def test_dlq_entry_no_phone_in_any_field() -> None:
    """DLQ 条目所有字段不含手机号明文。"""
    exc = RuntimeError("user phone 13800138000 failed")
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    [item] = list(_dlq.values())
    for field_name, field_value in item.items():
        if not isinstance(field_value, str):
            continue
        for regex in _PII_REGEXES:
            assert not regex.search(field_value), (
                f"字段 {field_name} 含 PII 明文: {field_value}"
            )


def test_dlq_entry_no_id_card_in_any_field() -> None:
    """DLQ 条目所有字段不含身份证明文。"""
    exc = RuntimeError("id 110101199003071234 invalid")
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    [item] = list(_dlq.values())
    for field_name, field_value in item.items():
        if not isinstance(field_value, str):
            continue
        for regex in _PII_REGEXES:
            assert not regex.search(field_value), (
                f"字段 {field_name} 含 PII 明文: {field_value}"
            )


def test_dlq_entry_no_bank_card_in_any_field() -> None:
    """DLQ 条目所有字段不含银行卡明文。"""
    exc = RuntimeError("card 6222020200112345 declined")
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    [item] = list(_dlq.values())
    for field_name, field_value in item.items():
        if not isinstance(field_value, str):
            continue
        for regex in _PII_REGEXES:
            assert not regex.search(field_value), (
                f"字段 {field_name} 含 PII 明文: {field_value}"
            )


def test_dlq_entry_no_email_in_any_field() -> None:
    """DLQ 条目所有字段不含邮箱明文。"""
    exc = RuntimeError("contact user@example.com failed")
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    [item] = list(_dlq.values())
    for field_name, field_value in item.items():
        if not isinstance(field_value, str):
            continue
        for regex in _PII_REGEXES:
            assert not regex.search(field_value), (
                f"字段 {field_name} 含 PII 明文: {field_value}"
            )


def test_dlq_entry_no_pii_with_mixed_content() -> None:
    """混合 PII 的异常 → DLQ 条目所有字段无 PII 明文。"""
    exc = RuntimeError(
        "contact 13800138000 id 110101199003071234 card 6222020200112345 email a@b.com"
    )
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    [item] = list(_dlq.values())
    for field_name, field_value in item.items():
        if not isinstance(field_value, str):
            continue
        for regex in _PII_REGEXES:
            assert not regex.search(field_value), (
                f"字段 {field_name} 含 PII 明文: {field_value}"
            )


# ── 3. DLQ 条目字段集合契约 ──


def test_dlq_entry_only_contains_allowed_fields() -> None:
    """DLQ 条目只存：唯一键、错误码、脱敏摘要、时间戳 + scope/retry 元数据。

    不存输入数据正文、凭据、PII 明细。
    """
    handle_failure(_FakePipeline(), TEST_SCOPE, RuntimeError("boom"))

    [item] = list(_dlq.values())

    # 必须存在的字段（唯一键、错误码、脱敏摘要、时间戳）
    required_keys = {"id", "pipelineId", "errorCode", "reason", "createdAt"}
    assert required_keys.issubset(item.keys()), (
        f"DLQ 条目缺少必要字段: {required_keys - set(item.keys())}"
    )

    # 禁止存在的字段（输入数据正文、凭据）
    forbidden_keys = {
        "input", "input_data", "payload", "credentials", "body",
        "sample_input", "raw_input", "request_body", "headers",
        "token", "password", "secret", "api_key",
    }
    actual_forbidden = forbidden_keys & set(item.keys())
    assert not actual_forbidden, (
        f"DLQ 条目含禁止字段: {actual_forbidden}"
    )


def test_dlq_entry_reason_is_sanitized() -> None:
    """DLQ 条目的 reason 字段是脱敏后的摘要（不含 PII 明文）。"""
    exc = RuntimeError("user 13800138000 failed at a@b.com")
    handle_failure(_FakePipeline(), TEST_SCOPE, exc)

    [item] = list(_dlq.values())
    reason = item["reason"]
    assert "13800138000" not in reason
    assert "a@b.com" not in reason
    assert "***" in reason


# ── 4. 正则扫描 DLQ 条目（端到端 PII 泄漏检测） ──


def test_scan_all_dlq_entries_for_pii() -> None:
    """扫描 DLQ 中所有条目，确认无 PII 明文泄漏。

    模拟安全扫描：投递多条含 PII 的失败 → 扫描所有 DLQ 条目。
    """
    # 投递多条含不同 PII 的失败
    handle_failure(_FakePipeline("p1"), TEST_SCOPE, RuntimeError("phone 13800138000"))
    handle_failure(_FakePipeline("p2"), TEST_SCOPE, RuntimeError("id 110101199003071234"))
    handle_failure(_FakePipeline("p3"), TEST_SCOPE, RuntimeError("card 6222020200112345"))
    handle_failure(_FakePipeline("p4"), TEST_SCOPE, RuntimeError("mail a@b.com"))

    assert len(_dlq) == 4

    # 扫描所有 DLQ 条目的所有字符串字段
    for key, item in _dlq.items():
        for field_name, field_value in item.items():
            if not isinstance(field_value, str):
                continue
            for regex in _PII_REGEXES:
                assert not regex.search(field_value), (
                    f"DLQ 条目 {key} 字段 {field_name} 含 PII 明文: {field_value}"
                )


def test_pii_scan_covers_dlq_id_and_pipeline_id_fields() -> None:
    """PII 扫描覆盖 DLQ 条目的 id / pipelineId 字段（这些字段也可能被注入 PII）。"""
    # pipelineId 是 _FakePipeline.id，构造时不含 PII
    handle_failure(_FakePipeline("pipe-clean"), TEST_SCOPE, RuntimeError("clean error"))

    [item] = list(_dlq.values())
    # 扫描 id / pipelineId 字段
    for field_name in ("id", "pipelineId"):
        value = item[field_name]
        for regex in _PII_REGEXES:
            assert not regex.search(value), (
                f"字段 {field_name} 含 PII 明文: {value}"
            )
