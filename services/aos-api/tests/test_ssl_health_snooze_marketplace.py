"""W2-BK · SSL / Health Snooze / Context Panel / Marketplace 引擎组测试（#10 #11 #12 #13）.

覆盖 SslCertificateEngine / HealthSnoozeEngine / HealthContextPanelEngine /
HealthMarketplaceEngine 四引擎，以及单例 getter。
"""
from __future__ import annotations

import time

import pytest

from aos_api.ssl_health_snooze_marketplace import (
    ContextEntry,
    HealthCheckProduct,
    HealthContextPanelEngine,
    HealthMarketplaceEngine,
    HealthSnoozeEngine,
    SnoozeHistoryEntry,
    SnoozeRecord,
    SslCertificate,
    SslCertificateEngine,
    SslHealthSnoozeError,
    get_health_context_panel_engine,
    get_health_marketplace_engine,
    get_health_snooze_engine,
    get_ssl_certificate_engine,
)


# ════════════════════ #10 SslCertificateEngine ════════════════════


class TestSslCertificateEngine:
    def setup_method(self) -> None:
        self.eng = SslCertificateEngine()

    def test_register_cert(self) -> None:
        before = time.time()
        cert = self.eng.register_cert(
            "agent-1",
            "example.com",
            valid_from=1000.0,
            valid_until=2000.0,
            issuer="Iss",
            serial_number="SN",
            fingerprint="FP",
            auto_renew=True,
        )
        after = time.time()
        assert isinstance(cert, SslCertificate)
        assert cert.id.startswith("cert-")
        assert cert.agent_id == "agent-1"
        assert cert.common_name == "example.com"
        assert cert.valid_from == 1000.0
        assert cert.valid_until == 2000.0
        assert cert.issuer == "Iss"
        assert cert.serial_number == "SN"
        assert cert.fingerprint == "FP"
        assert cert.auto_renew is True
        assert cert.status == "active"
        assert before <= cert.created_at <= after
        assert self.eng.get_cert(cert.id).id == cert.id

    def test_get_cert(self) -> None:
        cert = self.eng.register_cert("agent-1", "cn")
        got = self.eng.get_cert(cert.id)
        assert isinstance(got, SslCertificate)
        assert got.id == cert.id
        assert got.common_name == "cn"

    def test_get_cert_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.get_cert("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_certs(self) -> None:
        c1 = self.eng.register_cert("agent-1", "cn1")
        c2 = self.eng.register_cert("agent-2", "cn2")
        c3 = self.eng.register_cert("agent-1", "cn3")
        self.eng.revoke_cert(c3.id)
        # 全部
        assert len(self.eng.list_certs()) == 3
        # 按 agent_id 过滤
        agent1 = self.eng.list_certs(agent_id="agent-1")
        assert len(agent1) == 2
        assert all(c.agent_id == "agent-1" for c in agent1)
        # 按 status 过滤
        assert len(self.eng.list_certs(status="revoked")) == 1
        assert len(self.eng.list_certs(status="active")) == 2
        # 组合过滤
        assert len(self.eng.list_certs(agent_id="agent-1", status="revoked")) == 1
        # 结果按 created_at 排序
        assert self.eng.list_certs() == sorted(
            self.eng.list_certs(), key=lambda c: c.created_at
        )

    def test_update_cert(self) -> None:
        cert = self.eng.register_cert("agent-1", "cn-old", issuer="iss")
        updated = self.eng.update_cert(
            cert.id,
            {
                "common_name": "cn-new",
                "status": "expired",
                "id": "should-not-change",
                "nonexistent_field": "ignored",
            },
        )
        assert updated.common_name == "cn-new"
        assert updated.status == "expired"
        assert updated.id == cert.id  # id 不可改
        assert updated.issuer == "iss"  # 未传字段保留
        assert self.eng.get_cert(cert.id).common_name == "cn-new"

    def test_update_cert_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.update_cert("nope", {"common_name": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_revoke_cert(self) -> None:
        cert = self.eng.register_cert("agent-1", "cn")
        assert cert.status == "active"
        revoked = self.eng.revoke_cert(cert.id)
        assert revoked.status == "revoked"
        assert self.eng.get_cert(cert.id).status == "revoked"

    def test_revoke_cert_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.revoke_cert("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_check_expiry(self) -> None:
        future = time.time() + 60 * 86400  # 60 天后
        cert = self.eng.register_cert("agent-1", "cn", valid_until=future)
        result = self.eng.check_expiry(cert.id)
        assert result["cert_id"] == cert.id
        assert 59 <= result["days_remaining"] <= 60
        assert result["is_expired"] is False
        assert result["is_expiring_soon"] is False

    def test_check_expiry_expired(self) -> None:
        past = time.time() - 2 * 86400  # 2 天前
        cert = self.eng.register_cert("agent-1", "cn", valid_until=past)
        result = self.eng.check_expiry(cert.id)
        assert result["is_expired"] is True
        assert result["days_remaining"] < 0
        assert result["is_expiring_soon"] is True

    def test_check_expiry_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.check_expiry("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_renew_cert(self) -> None:
        cert = self.eng.register_cert("agent-1", "cn", valid_until=time.time() - 100)
        self.eng.revoke_cert(cert.id)  # 先吊销
        assert self.eng.get_cert(cert.id).status == "revoked"
        future = time.time() + 30 * 86400
        renewed = self.eng.renew_cert(cert.id, future)
        assert renewed.valid_until == future
        assert renewed.status == "active"
        assert self.eng.get_cert(cert.id).status == "active"

    def test_renew_cert_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.renew_cert("nope", 1.0)
        assert exc.value.code == "NOT_FOUND"

    def test_delete_cert(self) -> None:
        cert = self.eng.register_cert("agent-1", "cn")
        assert self.eng.delete_cert(cert.id) is True
        assert self.eng.delete_cert(cert.id) is False  # 已删除
        with pytest.raises(SslHealthSnoozeError):
            self.eng.get_cert(cert.id)

    def test_fifo_eviction(self) -> None:
        max_certs = SslCertificateEngine._MAX_CERTS
        for i in range(max_certs + 5):
            self.eng.register_cert(f"agent-{i}", f"cn-{i}")
        assert len(self.eng.list_certs()) == max_certs


# ════════════════════ #11 HealthSnoozeEngine ════════════════════


class TestHealthSnoozeEngine:
    def setup_method(self) -> None:
        self.eng = HealthSnoozeEngine()

    def test_snooze(self) -> None:
        before = time.time()
        record = self.eng.snooze("chk-1", "user-1", 3600, reason="maintenance")
        after = time.time()
        assert isinstance(record, SnoozeRecord)
        assert record.id.startswith("snooze-")
        assert record.check_id == "chk-1"
        assert record.snoozed_by == "user-1"
        assert record.reason == "maintenance"
        assert record.duration_seconds == 3600
        assert before + 3600 <= record.snoozed_until <= after + 3600
        assert self.eng.get_active_snooze("chk-1") is not None

    def test_batch_snooze(self) -> None:
        records = self.eng.batch_snooze(
            ["chk-1", "chk-2", "chk-3"], "user-1", 3600, reason="batch"
        )
        assert len(records) == 3
        assert [r.check_id for r in records] == ["chk-1", "chk-2", "chk-3"]
        for r in records:
            assert r.duration_seconds == 3600
            assert r.reason == "batch"
            assert self.eng.get_active_snooze(r.check_id) is not None
        # 批量打盹应写入 3 条历史
        assert len(self.eng.list_history()) == 3

    def test_unsnooze(self) -> None:
        record = self.eng.snooze("chk-1", "user-1", 3600)
        assert self.eng.unsnooze("chk-1", "user-2") is True
        assert self.eng.get_active_snooze("chk-1") is None
        # 历史中应存在 unsnoozed 动作
        hist = self.eng.list_history("chk-1")
        assert any(h.action == "unsnoozed" for h in hist)

    def test_unsnooze_not_found(self) -> None:
        assert self.eng.unsnooze("chk-1", "user-1") is False

    def test_get_active_snooze(self) -> None:
        self.eng.snooze("chk-1", "user-1", 3600)
        active = self.eng.get_active_snooze("chk-1")
        assert active is not None
        assert isinstance(active, SnoozeRecord)
        assert active.check_id == "chk-1"

    def test_get_active_snooze_expired(self) -> None:
        record = self.eng.snooze("chk-1", "user-1", 3600)
        # 直接操作时间戳模拟过期（record 与存储为同一对象引用）
        record.snoozed_until = time.time() - 1
        assert self.eng.get_active_snooze("chk-1") is None

    def test_list_snoozes(self) -> None:
        r1 = self.eng.snooze("chk-1", "u", 3600)
        self.eng.snooze("chk-2", "u", 3600)
        r3 = self.eng.snooze("chk-1", "u", 3600)
        # 让 r1 过期
        r1.snoozed_until = time.time() - 1
        # 默认仅活跃、按 check_id 过滤
        active_chk1 = self.eng.list_snoozes("chk-1")
        assert len(active_chk1) == 1
        assert active_chk1[0].id == r3.id
        # include_expired=True 返回全部 chk-1
        all_chk1 = self.eng.list_snoozes("chk-1", include_expired=True)
        assert len(all_chk1) == 2
        # 结果按 created_at 排序
        assert all_chk1 == sorted(all_chk1, key=lambda r: r.created_at)

    def test_list_history(self) -> None:
        self.eng.snooze("chk-1", "u1", 3600)
        self.eng.snooze("chk-2", "u2", 3600)
        self.eng.unsnooze("chk-1", "u3")
        all_hist = self.eng.list_history()
        assert len(all_hist) == 3
        assert all(isinstance(h, SnoozeHistoryEntry) for h in all_hist)
        chk1_hist = self.eng.list_history("chk-1")
        assert len(chk1_hist) == 2
        assert all(h.check_id == "chk-1" for h in chk1_hist)
        # 按时间戳排序
        assert chk1_hist == sorted(chk1_hist, key=lambda h: h.timestamp)

    def test_cleanup_expired(self) -> None:
        r1 = self.eng.snooze("chk-1", "user-1", 3600)
        r2 = self.eng.snooze("chk-2", "user-1", 3600)
        # 让两个都过期
        r1.snoozed_until = time.time() - 1
        r2.snoozed_until = time.time() - 1
        count = self.eng.cleanup_expired()
        assert count == 2
        assert len(self.eng.list_snoozes(include_expired=True)) == 0
        # 过期清理应写入 expired 历史动作
        actions = [h.action for h in self.eng.list_history()]
        assert actions.count("expired") == 2

    def test_cleanup_expired_none(self) -> None:
        self.eng.snooze("chk-1", "u", 3600)  # 活跃
        assert self.eng.cleanup_expired() == 0

    def test_delete_snooze(self) -> None:
        record = self.eng.snooze("chk-1", "u", 3600)
        assert self.eng.delete_snooze(record.id) is True
        assert self.eng.delete_snooze(record.id) is False  # 已删除
        assert self.eng.get_active_snooze("chk-1") is None

    def test_fifo_eviction_snoozes(self) -> None:
        max_snoozes = HealthSnoozeEngine._MAX_SNOOZES
        for i in range(max_snoozes + 5):
            self.eng.snooze(f"chk-{i}", "user-1", 3600)
        assert len(self.eng.list_snoozes(include_expired=True)) == max_snoozes

    def test_history_fifo_eviction(self) -> None:
        max_history = HealthSnoozeEngine._MAX_HISTORY
        for _ in range(max_history + 5):
            self.eng._add_history("chk-1", "snoozed", "user-1")
        assert len(self.eng.list_history()) == max_history


# ════════════════════ #12 HealthContextPanelEngine ════════════════════


class TestHealthContextPanelEngine:
    def setup_method(self) -> None:
        self.eng = HealthContextPanelEngine()

    def test_add_entry(self) -> None:
        before = time.time()
        entry = self.eng.add_entry(
            "chk-1", "comment", "hello", "alice", {"k": "v"}
        )
        after = time.time()
        assert isinstance(entry, ContextEntry)
        assert entry.id.startswith("ctx-")
        assert entry.check_id == "chk-1"
        assert entry.entry_type == "comment"
        assert entry.content == "hello"
        assert entry.author == "alice"
        assert entry.metadata == {"k": "v"}
        assert before <= entry.created_at <= after
        assert self.eng.get_entry(entry.id).content == "hello"

    def test_add_entry_invalid_type(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.add_entry("chk-1", "invalid", "x", "u")
        assert exc.value.code == "INVALID_ENTRY_TYPE"

    def test_get_entry(self) -> None:
        entry = self.eng.add_entry("chk-1", "comment", "hi", "u")
        got = self.eng.get_entry(entry.id)
        assert isinstance(got, ContextEntry)
        assert got.id == entry.id
        assert got.content == "hi"

    def test_get_entry_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.get_entry("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_entries(self) -> None:
        self.eng.add_entry("chk-1", "comment", "a", "u")
        self.eng.add_entry("chk-1", "issue", "b", "u")
        self.eng.add_entry("chk-2", "comment", "c", "u")
        # 全部
        assert len(self.eng.list_entries()) == 3
        # 按 check_id 过滤
        assert len(self.eng.list_entries(check_id="chk-1")) == 2
        # 按 entry_type 过滤
        assert len(self.eng.list_entries(entry_type="comment")) == 2
        # 组合过滤
        assert len(self.eng.list_entries(check_id="chk-1", entry_type="comment")) == 1
        # 按 created_at 排序
        assert self.eng.list_entries() == sorted(
            self.eng.list_entries(), key=lambda e: e.created_at
        )

    def test_update_entry(self) -> None:
        entry = self.eng.add_entry("chk-1", "comment", "old", "u", {"a": 1})
        updated = self.eng.update_entry(entry.id, content="new", metadata={"b": 2})
        assert updated.content == "new"
        assert updated.metadata == {"b": 2}
        assert self.eng.get_entry(entry.id).content == "new"
        # 仅更新 content，metadata 保留
        updated2 = self.eng.update_entry(entry.id, content="newer")
        assert updated2.content == "newer"
        assert updated2.metadata == {"b": 2}

    def test_update_entry_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.update_entry("nope", content="x")
        assert exc.value.code == "NOT_FOUND"

    def test_delete_entry(self) -> None:
        entry = self.eng.add_entry("chk-1", "comment", "x", "u")
        assert self.eng.delete_entry(entry.id) is True
        assert self.eng.delete_entry(entry.id) is False  # 已删除
        with pytest.raises(SslHealthSnoozeError):
            self.eng.get_entry(entry.id)

    def test_get_context_summary(self) -> None:
        e1 = self.eng.add_entry("chk-1", "comment", "a", "u")
        e2 = self.eng.add_entry("chk-1", "comment", "b", "u")
        e3 = self.eng.add_entry("chk-1", "issue", "c", "u")
        self.eng.add_entry("chk-2", "comment", "d", "u")  # 其他 check 不计入
        summary = self.eng.get_context_summary("chk-1")
        assert summary["check_id"] == "chk-1"
        assert summary["total_entries"] == 3
        assert summary["by_type"] == {
            "comment": 2,
            "issue": 1,
            "plan": 0,
            "source": 0,
        }
        assert summary["latest_entry_at"] == max(
            e1.created_at, e2.created_at, e3.created_at
        )
        # 空白 check 的摘要
        empty = self.eng.get_context_summary("chk-9")
        assert empty["total_entries"] == 0
        assert empty["by_type"] == {
            "comment": 0,
            "issue": 0,
            "plan": 0,
            "source": 0,
        }
        assert empty["latest_entry_at"] is None

    def test_fifo_eviction(self) -> None:
        max_entries = HealthContextPanelEngine._MAX_ENTRIES
        for i in range(max_entries + 5):
            self.eng.add_entry(f"chk-{i}", "comment", f"c-{i}", "u")
        assert len(self.eng.list_entries()) == max_entries


# ════════════════════ #13 HealthMarketplaceEngine ════════════════════


class TestHealthMarketplaceEngine:
    def setup_method(self) -> None:
        self.eng = HealthMarketplaceEngine()

    def test_integrate_check(self) -> None:
        before = time.time()
        product = self.eng.integrate_check(
            "chk-1",
            "prod-1",
            "Product One",
            "Check A",
            "desc",
            "warning",
        )
        after = time.time()
        assert isinstance(product, HealthCheckProduct)
        assert product.id.startswith("hcp-")
        assert product.check_id == "chk-1"
        assert product.product_id == "prod-1"
        assert product.product_name == "Product One"
        assert product.check_name == "Check A"
        assert product.check_description == "desc"
        assert product.severity_level == "warning"
        assert product.enabled is True
        assert before <= product.integrated_at <= after
        assert self.eng.get_product("prod-1").product_id == "prod-1"

    def test_integrate_check_invalid_severity(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.integrate_check("chk-1", "prod-1", "P", "C", severity_level="bad")
        assert exc.value.code == "INVALID_SEVERITY"

    def test_get_product(self) -> None:
        self.eng.integrate_check("chk-1", "prod-1", "P", "C")
        got = self.eng.get_product("prod-1")
        assert isinstance(got, HealthCheckProduct)
        assert got.product_id == "prod-1"
        assert got.check_id == "chk-1"

    def test_get_product_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.get_product("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_list_products(self) -> None:
        self.eng.integrate_check("chk-1", "p1", "P1", "C1", severity_level="info")
        self.eng.integrate_check("chk-1", "p2", "P2", "C2", severity_level="warning")
        self.eng.integrate_check("chk-2", "p3", "P3", "C3", severity_level="critical")
        # 全部
        assert len(self.eng.list_products()) == 3
        # 按 product_id 过滤
        assert len(self.eng.list_products(product_id="p1")) == 1
        # 按 check_id 过滤
        assert len(self.eng.list_products(check_id="chk-1")) == 2
        # 按 severity_level 过滤
        assert len(self.eng.list_products(severity_level="warning")) == 1
        # 组合过滤
        assert (
            len(self.eng.list_products(check_id="chk-1", severity_level="info")) == 1
        )
        # 按 integrated_at 排序
        assert self.eng.list_products() == sorted(
            self.eng.list_products(), key=lambda p: p.integrated_at
        )

    def test_update_product(self) -> None:
        self.eng.integrate_check("chk-1", "p1", "P1", "C1", severity_level="info")
        updated = self.eng.update_product(
            "p1",
            {
                "product_name": "P1-new",
                "severity_level": "critical",
                "product_id": "should-not-change",
                "id": "should-not-change",
            },
        )
        assert updated.product_name == "P1-new"
        assert updated.severity_level == "critical"
        assert updated.product_id == "p1"  # product_id 不可改
        assert self.eng.get_product("p1").product_name == "P1-new"

    def test_update_product_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.update_product("nope", {"product_name": "x"})
        assert exc.value.code == "NOT_FOUND"

    def test_enable_product(self) -> None:
        self.eng.integrate_check("chk-1", "p1", "P1", "C1")
        disabled = self.eng.disable_product("p1")
        assert disabled.enabled is False
        assert self.eng.get_product("p1").enabled is False
        enabled = self.eng.enable_product("p1")
        assert enabled.enabled is True
        assert self.eng.get_product("p1").enabled is True

    def test_disable_product_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.disable_product("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_enable_product_not_found(self) -> None:
        with pytest.raises(SslHealthSnoozeError) as exc:
            self.eng.enable_product("nope")
        assert exc.value.code == "NOT_FOUND"

    def test_delete_product(self) -> None:
        self.eng.integrate_check("chk-1", "p1", "P1", "C1")
        assert self.eng.delete_product("p1") is True
        assert self.eng.delete_product("p1") is False  # 已删除
        with pytest.raises(SslHealthSnoozeError):
            self.eng.get_product("p1")

    def test_fifo_eviction(self) -> None:
        max_products = HealthMarketplaceEngine._MAX_PRODUCTS
        # 必须用不同 product_id，否则会覆盖而非触发 FIFO
        for i in range(max_products + 5):
            self.eng.integrate_check(f"chk-{i}", f"prod-{i}", f"P{i}", f"C{i}")
        assert len(self.eng.list_products()) == max_products


# ════════════════════ 单例 getter ════════════════════


def test_singleton_getters() -> None:
    assert get_ssl_certificate_engine() is get_ssl_certificate_engine()
    assert get_health_snooze_engine() is get_health_snooze_engine()
    assert get_health_context_panel_engine() is get_health_context_panel_engine()
    assert get_health_marketplace_engine() is get_health_marketplace_engine()
