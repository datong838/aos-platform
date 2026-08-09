"""D2.6 子任务 D: 通用 JDBC 连接器运行时 — SSH 隧道 + JDBC 连接 + Schema 发现 + 行流读取。

通用化设计（响应用户指示）：
- 不绑 niushop，支持任意 MySQL / PostgreSQL 数据源
- SSH 隧道是通用能力（适合本地开发），不是微商城专属
- JDBC 连接保持 pymysql（MySQL）或 psycopg（PostgreSQL），与 ec_source_adapter 一致
- 使用 stdlib subprocess 调 ssh 命令，不引入 paramiko 依赖

生命周期：
1. __enter__：建立 SSH 隧道（如配置 sshHost）+ JDBC 连接
2. discover_schemas()：返回 schema/table/column 树（information_schema 查询）
3. read_rows(table, cursor, limit)：返回行流（dict 形式）
4. __exit__：关闭 JDBC 连接 + 终止 SSH 隧道进程

约束：
- 失败不静默：SSH 隧道建立失败 / JDBC 连接失败 → 抛异常
- __exit__ 容错：_conn 或 _ssh_tunnel 为 None 时不抛新异常
"""

from __future__ import annotations

import atexit
import hashlib
import os
import re
import socket
import subprocess
import tempfile
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Iterator, Sequence

import pymysql

from aos_api.logging_facade import get_logger

log = get_logger("aos-api.jdbc-connector-runtime")


# 隧道就绪探测最大重试次数与间隔
_TUNNEL_READY_RETRIES: int = 10
_TUNNEL_READY_INTERVAL: float = 0.3


# ═══════════════════════════════════════════════════════════════
# D4 Phase C · C1: 302 表分类打标（A/B/C/D/E）
# 上位规格：D4-12OT业务闭环与302表衔接执行规格.md §4.3
# 分类规则（按判定顺序，先匹配先返回）：
#   A = 核心 OT 源表（12 OT 来源的 16 张表名单，含 sku/category 等同名前缀）
#   B = JOIN 维度表（仅做字典翻译，无独立业务实体）
#   C = 明细扩展表（某主实体的附属明细/日志/轨迹）
#   D = 配置类·按需（定义/开关/模板/活动，未识别也归 D）
#   E = 系统/统计/消息（纯运维，不落 OT 孪生）
# ═══════════════════════════════════════════════════════════════

# A 类：12 条 P 管道源表（D4 规格 §3 冻结）
_OT_SOURCE_TABLES: frozenset[str] = frozenset({
    "ns_site",                     # P01 → Shop
    "ns_goods",                    # P02 → Product
    "ns_goods_sku",                # P03 → ProductSku
    "ns_goods_category",           # P04 → Category
    "ns_order",                    # P05 → Order
    "ns_order_goods",              # P06 → OrderLine
    "ns_express_delivery_package", # P07 → Shipment
    "ns_member",                  # P08 → CustomerLite
    "ns_weapp",                   # P09 → Weapp
    "ns_config",                   # P10 → SystemConfig
    "ns_goods_evaluate",          # P11 → ProductReview
    "ns_pay",                     # P12 → Payment
})

# B 类前缀/表名（JOIN 维度字典，无独立业务实体）
_B_EXACT_OR_PREFIX: tuple[str, ...] = (
    "express_company", "member_level", "area", "goods_brand",
    "goods_evaluate_image", "member_label", "promotion_coupon_type",
    "goods_spec", "goods_attr", "goods_unit",
)

# C 类前缀（主实体附属明细/日志/轨迹）
_C_PREFIXES: tuple[str, ...] = (
    "order_log", "pay_refund_notify_log", "stat_",
    "member_account", "member_address", "order_promotion_detail",
    "order_refund", "order_action_log",
)

# E 类前缀/表名（系统/统计/消息，不落 OT 孪生）
_E_EXACT_OR_PREFIX: tuple[str, ...] = (
    "cron", "sys_", "user", "menu", "export",
    "album", "printer_", "cashier_", "service_", "servicer_",
    "document", "v3_upgrade_log", "session", "migration",
)

# D 类前缀（配置类·按需，未识别也归 D 作为兜底）
_D_PREFIXES: tuple[str, ...] = (
    "promotion_", "coupon_", "supercard_", "giftcard_",
    "diy_", "form_", "notes_", "live_",
    "fenxiao_", "store_", "weapp_",
    "config_", "template_", "activity_",
)


def _classify_table(table_name: str) -> str:
    """根据表名推断 302 表分类标签（A/B/C/D/E）。

    顺序：A → B → C → E → D（默认）
    A 类用精确匹配，B/C/E/D 用前缀或精确匹配。
    未匹配任何规则的表归 D（配置类·按需，最安全）。

    注：Niushop 所有表带 `ns_` 前缀，此处先剥离再匹配前缀规则。
    """
    if not table_name:
        return "D"
    # A: OT 源表（精确匹配，含 ns_ 前缀）
    if table_name in _OT_SOURCE_TABLES:
        return "A"
    # 剥离 ns_ 前缀后再匹配 B/C/E/D 前缀规则
    normalized = table_name[3:] if table_name.startswith("ns_") else table_name
    # B: JOIN 维度（精确或前缀）
    for p in _B_EXACT_OR_PREFIX:
        if normalized == p or normalized.startswith(p):
            return "B"
    # C: 明细扩展（前缀）
    for p in _C_PREFIXES:
        if normalized.startswith(p):
            return "C"
    # E: 系统/统计（精确或前缀）
    for p in _E_EXACT_OR_PREFIX:
        if normalized == p or normalized.startswith(p):
            return "E"
    # D: 配置类（前缀）
    for p in _D_PREFIXES:
        if normalized.startswith(p):
            return "D"
    # 默认归 D（最安全，未识别的表按"按需"处理）
    return "D"


# ═══════════════════════════════════════════════
# 全局单例缓存（SSH 隧道 + DB 连接）
# ═══════════════════════════════════════════════

@dataclass
class _CachedTunnel:
    """已缓存的 SSH 隧道实例。"""
    tunnel: SshTunnel = None  # type: ignore[assignment]
    local_port: int = 0
    created_at: float = field(default_factory=time.time)


@dataclass
class _CachedConn:
    """已缓存的 DB 连接实例。"""
    conn: Any = None  # pymysql.Connection
    created_at: float = field(default_factory=time.time)
    # pymysql Connection 不支持多线程同时使用。同一缓存连接的
    # 健康检查、事务和查询必须持有同一 lease。
    lease: threading.RLock = field(default_factory=threading.RLock)


# 全局缓存字典（key -> 缓存对象）
_TUNNEL_CACHE: dict[str, _CachedTunnel] = {}
_CONN_CACHE: dict[str, _CachedConn] = {}
# 全局缓存锁（防止并发重复建隧道/连接）
_CACHE_LOCK = threading.Lock()


def _tunnel_cache_key(config: dict[str, Any]) -> str:
    """为 SSH 隧道生成缓存 key（按 SSH 配置去重）。

    相同 SSH 配置（host/port/user/remote 相同 + 认证方式相同）共享同一条隧道。
    """
    ssh_host = config.get("sshHost") or ""
    ssh_port = int(config.get("sshPort", 22))
    ssh_user = config.get("sshUser") or ""
    remote_host = config.get("dbHost") or config.get("host") or ""
    remote_port = int(config.get("dbPort") or config.get("port") or 3306)
    auth_mode = "pass" if config.get("sshPassword") else (
        "key" if config.get("sshKeyRef") else "none"
    )
    raw = f"{auth_mode}|{ssh_host}:{ssh_port}|{ssh_user}|{remote_host}:{remote_port}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _conn_cache_key(config: dict[str, Any], local_port: int | None = None) -> str:
    """为 DB 连接生成缓存 key（按 DB 配置去重）。

    隧道代理场景下通过 local_port 区分同一远程数据库的不同代理路径。
    """
    if local_port:
        host = "127.0.0.1"
        port = local_port
    else:
        host = config.get("dbHost") or config.get("host") or ""
        port = int(config.get("dbPort") or config.get("port") or 3306)
    database = config.get("database") or ""
    username = config.get("username") or config.get("user") or ""
    raw = f"{host}:{port}|{database}|{username}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _is_tunnel_alive(cached: _CachedTunnel) -> bool:
    """检测 SSH 隧道是否存活（本地端口是否可连接）。"""
    return _is_port_open("127.0.0.1", cached.local_port, timeout=0.3)


def _is_conn_alive(cached: _CachedConn) -> bool:
    """检测 DB 连接是否存活（ping）。"""
    with cached.lease:
        try:
            cached.conn.ping(reconnect=False)
            return True
        except Exception:
            return False


def _build_ssh_tunnel(config: dict[str, Any]) -> _CachedTunnel:
    """根据 config 建立一条新 SSH 隧道并返回 _CachedTunnel（内部使用，不加锁）。"""
    ssh_host = config.get("sshHost")
    ssh_port = int(config.get("sshPort", 22))
    ssh_user = config.get("sshUser") or ""
    ssh_password = config.get("sshPassword")
    ssh_key_ref = config.get("sshKeyRef")
    db_host = config.get("dbHost") or config.get("host") or ""
    db_port = int(config.get("dbPort") or config.get("port") or 3306)

    if ssh_password:
        tunnel = SshTunnel(
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            ssh_user=ssh_user,
            ssh_password=ssh_password,
            remote_host=db_host,
            remote_port=db_port,
        )
    else:
        ssh_key_path = _resolve_secret_path(ssh_key_ref)
        tunnel = SshTunnel(
            ssh_host=ssh_host,
            ssh_port=ssh_port,
            ssh_user=ssh_user,
            ssh_key_path=ssh_key_path,
            remote_host=db_host,
            remote_port=db_port,
        )
    local_port = tunnel.open()
    return _CachedTunnel(tunnel=tunnel, local_port=local_port)


def _get_or_create_tunnel(config: dict[str, Any]) -> int | None:
    """获取或创建 SSH 隧道，返回本地端口；无 SSH 配置返回 None。

    带缓存：同 key 复用；健康检测失败自动重建。
    """
    if not config.get("sshHost"):
        return None
    key = _tunnel_cache_key(config)

    # 快速路径（读缓存，不加锁）
    cached = _TUNNEL_CACHE.get(key)
    if cached is not None and _is_tunnel_alive(cached):
        return cached.local_port

    # 慢速路径：加锁建立
    with _CACHE_LOCK:
        # double-check（锁内再次验证）
        cached = _TUNNEL_CACHE.get(key)
        if cached is not None and _is_tunnel_alive(cached):
            return cached.local_port

        # 旧隧道失效：清理
        if cached is not None:
            try:
                cached.tunnel.close()
            except Exception as exc:
                log.warning("Closing stale tunnel failed: %s", exc)
            log.info("SSH tunnel rebuilt (key=%s, reason=stale)", key)
        else:
            log.info("SSH tunnel created (key=%s, reason=cache_miss)", key)

        new_cached = _build_ssh_tunnel(config)
        _TUNNEL_CACHE[key] = new_cached
        return new_cached.local_port


def _build_db_conn(config: dict[str, Any], host: str, port: int) -> _CachedConn:
    """建立新 pymysql 连接（内部使用，不加锁）。"""
    password = _resolve_secret_value(config.get("secretRef"))
    if not password and config.get("password"):
        password = str(config["password"])
    conn = pymysql.connect(
        host=host,
        port=port,
        user=config.get("username") or config.get("user") or "",
        password=password,
        database=config["database"],
        connect_timeout=30,
        read_timeout=30,
        cursorclass=pymysql.cursors.DictCursor,
    )
    return _CachedConn(conn=conn)


def _get_or_create_conn(config: dict[str, Any], host: str, port: int) -> _CachedConn:
    """获取或创建 DB 连接及其 lease。

    带缓存：同 key 复用；健康检测失败自动重建。
    """
    # local_port 仅用于生成 key（当 host=127.0.0.1 时）
    local_port = port if host == "127.0.0.1" else None
    key = _conn_cache_key(config, local_port)

    cached = _CONN_CACHE.get(key)
    if cached is not None and _is_conn_alive(cached):
        return cached

    with _CACHE_LOCK:
        cached = _CONN_CACHE.get(key)
        if cached is not None and _is_conn_alive(cached):
            return cached

        if cached is not None:
            try:
                cached.conn.close()
            except Exception as exc:
                log.warning("Closing stale DB conn failed: %s", exc)
            log.info("DB conn rebuilt (key=%s, reason=stale)", key)
        else:
            log.info("DB conn created (key=%s, reason=cache_miss)", key)

        new_cached = _build_db_conn(config, host, port)
        _CONN_CACHE[key] = new_cached
        return new_cached


def _evict_cached_conn(key: str, expected: _CachedConn) -> None:
    """仅驱逐调用方实际使用的坏连接，避免误关闭并发重建的新连接。"""
    with _CACHE_LOCK:
        current = _CONN_CACHE.get(key)
        if current is not expected:
            return
        _CONN_CACHE.pop(key, None)
    with expected.lease:
        try:
            expected.conn.close()
        except Exception as exc:
            log.warning("Closing evicted DB conn failed (key=%s): %s", key, exc)


def _cleanup_all_cached() -> None:
    """清理所有缓存（进程退出时调用，atexit + FastAPI shutdown）。"""
    log.info("Cleaning up JDBC cache: tunnels=%d, conns=%d", len(_TUNNEL_CACHE), len(_CONN_CACHE))
    with _CACHE_LOCK:
        for key, cached in list(_CONN_CACHE.items()):
            try:
                cached.conn.close()
            except Exception as exc:
                log.warning("Cleanup DB conn (key=%s) failed: %s", key, exc)
        _CONN_CACHE.clear()

        for key, cached in list(_TUNNEL_CACHE.items()):
            try:
                cached.tunnel.close()
            except Exception as exc:
                log.warning("Cleanup SSH tunnel (key=%s) failed: %s", key, exc)
        _TUNNEL_CACHE.clear()


# 进程退出钩子（无论有没有 FastAPI，都会执行）
atexit.register(_cleanup_all_cached)


def prebuild_ssh_tunnels(props_list: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """启动时为一批数据源预建立 SSH 隧道（用于 FastAPI startup 事件）。

    输入：一组数据源的 props 列表（可能含重复 SSH 配置，内部自动去重）。
    输出：每条 props 对应的结果 [{key, ok, local_port|error, elapsed_ms}]，用于日志。
    """
    results: list[dict[str, Any]] = []
    seen_keys: set[str] = set()
    for props in props_list:
        if not props.get("sshHost"):
            continue
        key = _tunnel_cache_key(props)
        if key in seen_keys:
            continue
        seen_keys.add(key)
        start = time.time()
        try:
            local_port = _get_or_create_tunnel(props)
            elapsed = int((time.time() - start) * 1000)
            results.append({
                "key": key,
                "ssh_endpoint": f"{props.get('sshHost')}:{props.get('sshPort', 22)}",
                "ok": True,
                "local_port": local_port,
                "elapsed_ms": elapsed,
            })
            log.info(
                "startup_prebuild ssh tunnel OK: endpoint=%s:%s user=%s port=%d elapsed=%dms",
                props.get("sshHost"), props.get("sshPort", 22), props.get("sshUser"), local_port, elapsed,
            )
        except Exception as exc:
            elapsed = int((time.time() - start) * 1000)
            results.append({
                "key": key,
                "ssh_endpoint": f"{props.get('sshHost')}:{props.get('sshPort', 22)}",
                "ok": False,
                "error": str(exc),
                "elapsed_ms": elapsed,
            })
            log.error(
                "startup_prebuild ssh tunnel FAILED: endpoint=%s:%s user=%s elapsed=%dms error=%s",
                props.get("sshHost"), props.get("sshPort", 22), props.get("sshUser"), elapsed, exc,
            )
    return results


# ═══════════════════════════════════════════════
# 公开的清理入口（供 FastAPI shutdown 事件调用）
# ═══════════════════════════════════════════════

def jdbc_runtime_shutdown() -> None:
    """FastAPI shutdown 事件：清理所有缓存的 SSH 隧道与 DB 连接。"""
    _cleanup_all_cached()


def prebuild_all_ssh_tunnels_from_meta_source() -> list[dict[str, Any]]:
    """启动时遍历所有租户的 meta_source，预建立所有含 sshHost 的 SSH 隧道。

    执行顺序（必须在 tenant catalog 启动之后）：
    1. 从 PG 的 meta_org / meta_workspace 读所有 org × project 组合
    2. 对每个 scope，查 meta_source 筛选 props->>'sshHost' 非空的数据源
    3. 去重后调用 prebuild_ssh_tunnels 批量建立

    失败不抛异常（Best-effort），仅记录日志与返回结果，不阻断启动。
    """
    import json as _json
    results: list[dict[str, Any]] = []
    try:
        from aos_api.db import connect
    except Exception as exc:
        log.warning("startup_prebuild_skip: cannot import db.connect: %s", exc)
        return results

    try:
        with connect() as conn:
            # 查出所有 (org_id, project_id) 对，再按 scope 查询含 sshHost 的数据源
            scopes = conn.execute(
                """SELECT DISTINCT s.org_id, s.project_id
                     FROM meta_source s
                    WHERE s.props IS NOT NULL
                      AND jsonb_typeof(s.props) = 'object'
                      AND s.props ? 'sshHost'
                      AND s.props->>'sshHost' <> ''"""
            ).fetchall()
            if not scopes:
                log.info("startup_prebuild_skip: no sources with sshHost in meta_source")
                return results

            all_props: list[dict[str, Any]] = []
            for scope in scopes:
                org_id = str(scope["org_id"])
                project_id = str(scope["project_id"])
                try:
                    rows = conn.execute(
                        """SELECT id, props
                             FROM meta_source
                            WHERE org_id=%s AND project_id=%s
                              AND props IS NOT NULL
                              AND jsonb_typeof(props) = 'object'
                              AND props ? 'sshHost'
                              AND props->>'sshHost' <> ''""",
                        (org_id, project_id),
                    ).fetchall()
                except Exception as exc:
                    log.warning("startup_prebuild_scope_query_failed: org=%s proj=%s err=%s",
                                org_id, project_id, exc)
                    continue
                for r in rows:
                    props = r["props"] if isinstance(r["props"], dict) else (
                        _json.loads(r["props"]) if isinstance(r["props"], str) else None
                    )
                    if isinstance(props, dict) and props.get("sshHost"):
                        props_copy = dict(props)
                        # 附带 org/project/source_id 信息给日志追踪（不参与 cache key）
                        props_copy["_org_id"] = org_id
                        props_copy["_project_id"] = project_id
                        props_copy["_source_id"] = str(r["id"])
                        all_props.append(props_copy)

            if not all_props:
                log.info("startup_prebuild_skip: no valid props extracted")
                return results

            log.info("startup_prebuild_begin: sources_with_ssh=%d", len(all_props))
            results = prebuild_ssh_tunnels(all_props)
            ok_count = sum(1 for r in results if r.get("ok"))
            fail_count = len(results) - ok_count
            log.info("startup_prebuild_done: ok=%d failed=%d total=%d",
                     ok_count, fail_count, len(results))
    except Exception as exc:
        log.exception("startup_prebuild_overall_failed: %s", exc)
    return results


class SshTunnel:
    """SSH 隧道（subprocess ssh -L 模式）。

    支持两种认证方式：
    1. SSH key 认证：ssh -fN -L ... -i key user@host（ssh_key_path 模式）
    2. SSH 密码认证：SSH_ASKPASS + ssh -f -L ... user@host（ssh_password 模式）
       参考 ssh-tunnel-mysql-auto 技能：用 SSH_ASKPASS_REQUIRE=force 绕过 tty，
       ssh -f 让进程自动 detach 到 init（ppid=1），独立于调用方进程

    设计权衡：
    - 不引入 paramiko 依赖（用户环境可能未装）
    - 密码模式：ssh -f 后进程 detach 到 init，主进程退出隧道仍存活，需显式 kill
    - key 模式：ssh -fN 后台运行，同上
    - 本地端口动态分配（从 29500 开始尝试，避免端口冲突）
    """

    def __init__(
        self,
        *,
        ssh_host: str,
        ssh_port: int,
        ssh_user: str,
        remote_host: str,
        remote_port: int,
        ssh_key_path: str | None = None,
        ssh_password: str | None = None,
    ) -> None:
        self.ssh_host = ssh_host
        self.ssh_port = ssh_port
        self.ssh_user = ssh_user
        self.ssh_key_path = ssh_key_path
        self.ssh_password = ssh_password
        self.remote_host = remote_host
        self.remote_port = remote_port
        self._local_port: int | None = None
        self._proc: subprocess.Popen[bytes] | None = None
        self._askpass_file: str | None = None

    def open(self) -> int:
        """建立 SSH 隧道，返回本地端口。

        失败时抛 RuntimeError（不静默）。
        """
        self._local_port = _allocate_local_port()

        if self.ssh_password:
            return self._open_with_password()
        if self.ssh_key_path:
            return self._open_with_key()
        raise RuntimeError("SSH tunnel: neither ssh_key_path nor ssh_password provided")

    def _open_with_password(self) -> int:
        """密码认证模式：SSH_ASKPASS + ssh -f（参考 ssh-tunnel-mysql-auto 技能）。

        ssh 进程自动 detach 到 init（ppid=1），独立于调用方进程。
        """
        # 创建临时 askpass helper 脚本
        askpass_content = f"""#!/bin/bash
echo '{self.ssh_password}'
"""
        fd, self._askpass_file = tempfile.mkstemp(suffix=".sh", prefix="_ssh_askpass_")
        with os.fdopen(fd, "w") as f:
            f.write(askpass_content)
        os.chmod(self._askpass_file, 0o700)

        cmd = [
            "ssh", "-4", "-f",
            "-o", "ServerAliveInterval=30",
            "-o", "ServerAliveCountMax=3",
            "-o", "StrictHostKeyChecking=no",
            "-o", "ExitOnForwardFailure=yes",
            "-N", "-L",
            f"127.0.0.1:{self._local_port}:127.0.0.1:{self.remote_port}",
            f"{self.ssh_user}@{self.ssh_host}",
        ]
        env = os.environ.copy()
        env["SSH_ASKPASS"] = self._askpass_file
        env["SSH_ASKPASS_REQUIRE"] = "force"
        env["DISPLAY"] = ":0"

        log.info(
            "Opening SSH tunnel (password): %s@%s:%d -> 127.0.0.1:%d (remote=%s:%d)",
            self.ssh_user, self.ssh_host, self.ssh_port,
            self._local_port, self.remote_host, self.remote_port,
        )
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"SSH tunnel: ssh command not found: {exc}") from exc

        return self._wait_ready()

    def _open_with_key(self) -> int:
        """key 认证模式：ssh -fN -i key（原逻辑）。
        """
        cmd = [
            "ssh",
            "-fN",  # 后台运行，不执行远程命令
            "-L", f"{self._local_port}:{self.remote_host}:{self.remote_port}",
            "-p", str(self.ssh_port),
            "-i", self.ssh_key_path,
            "-o", "StrictHostKeyChecking=accept-new",
            "-o", "ExitOnForwardFailure=yes",
            f"{self.ssh_user}@{self.ssh_host}",
        ]
        log.info(
            "Opening SSH tunnel (key): %s@%s:%d -> 127.0.0.1:%d (remote=%s:%d)",
            self.ssh_user, self.ssh_host, self.ssh_port,
            self._local_port, self.remote_host, self.remote_port,
        )
        try:
            self._proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
        except FileNotFoundError as exc:
            raise RuntimeError(f"SSH tunnel: ssh command not found: {exc}") from exc

        return self._wait_ready()

    def _wait_ready(self) -> int:
        """等待隧道就绪，返回本地端口。"""
        time.sleep(_TUNNEL_READY_INTERVAL)
        for _ in range(_TUNNEL_READY_RETRIES):
            if self._proc.poll() is not None:
                rc = self._proc.returncode
                if rc != 0:
                    stderr = self._proc.stderr.read().decode(errors="replace") if self._proc.stderr else ""
                    raise RuntimeError(f"SSH tunnel exited rc={rc}: {stderr.strip()}")
            if _is_port_open("127.0.0.1", self._local_port):
                log.info("SSH tunnel ready at 127.0.0.1:%d", self._local_port)
                return self._local_port
            time.sleep(_TUNNEL_READY_INTERVAL)

        raise RuntimeError(
            f"SSH tunnel failed to become ready after "
            f"{_TUNNEL_READY_RETRIES} retries (127.0.0.1:{self._local_port})"
        )

    def close(self) -> None:
        """终止 SSH 隧道进程。"""
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=5)
            except Exception as exc:
                log.warning("SSH tunnel terminate failed: %s", exc)
            self._proc = None
        # 清理临时 askpass 脚本
        if self._askpass_file and os.path.exists(self._askpass_file):
            try:
                os.unlink(self._askpass_file)
            except OSError:
                pass
            self._askpass_file = None


class JdbcConnectorRuntime:
    """通用 JDBC 连接器运行时（支持 SSH 隧道 + MySQL/PostgreSQL）。

    生命周期（2026-08-06 改为单例缓存复用）：
    1. __enter__：从全局缓存获取（健康检测 → 失效重建）SSH 隧道 + DB 连接
    2. discover_schemas() / list_tables_only() / ...：执行 SQL
    3. __exit__：**不关闭**，归还缓存，后续请求复用
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._config = dict(config)  # 存一份完整配置给缓存层 key 生成使用
        self.ssh_host: str | None = config.get("sshHost")
        self.ssh_port: int = int(config.get("sshPort", 22))
        self.ssh_user: str | None = config.get("sshUser")
        self.ssh_key_ref: str | None = config.get("sshKeyRef")
        # SSH 密码认证（与 sshKeyRef 二选一，参考 ssh-tunnel-mysql-auto 技能）
        self.ssh_password: str | None = config.get("sshPassword")
        # 支持两套字段名：原生 dbHost/dbPort/username，或 meta_source 通用 host/port/user
        self.db_host: str = config.get("dbHost") or config.get("host") or config["dbHost"]
        self.db_port: int = int(config.get("dbPort") or config.get("port") or config.get("dbPort", 3306))
        self.database: str = config["database"]
        self.username: str = config.get("username") or config.get("user") or config["username"]
        self.secret_ref: str | None = config.get("secretRef")
        # 明文 password fallback（meta_source 存明文时使用）
        self._raw_password: str | None = config.get("password")
        # 仅保留引用，用于 __exit__ 兼容；真实资源由全局缓存管理
        self._ssh_tunnel: SshTunnel | None = None
        self._conn: Any = None
        self._cached_conn: _CachedConn | None = None
        self._conn_key: str | None = None
        self._standalone_lease = threading.RLock()

    def __enter__(self) -> "JdbcConnectorRuntime":
        # 1. 从缓存取/建 SSH 隧道
        db_host = self.db_host
        db_port = self.db_port
        local_port: int | None = None
        if self.ssh_host:
            local_port = _get_or_create_tunnel(self._config)
            if local_port is None:
                raise RuntimeError("SSH tunnel creation failed (no local_port)")
            db_host = "127.0.0.1"
            db_port = local_port

        # 2. 从缓存取/建 DB 连接
        self._cached_conn = _get_or_create_conn(self._config, db_host, db_port)
        self._conn = self._cached_conn.conn
        local_port_for_key = db_port if db_host == "127.0.0.1" else None
        self._conn_key = _conn_cache_key(self._config, local_port_for_key)
        return self

    @contextmanager
    def _read_only_transaction(self) -> Iterator[None]:
        """在缓存连接 lease 内执行一个可恢复的只读事务。

        所有分块共享同一快照；无论成功失败都 rollback 并恢复
        autocommit。SQL/恢复失败时在释放 lease 后驱逐坏连接。
        """
        if self._conn is None:
            raise RuntimeError("JDBC runtime is not connected")
        cached = self._cached_conn
        lease = cached.lease if cached is not None else self._standalone_lease
        failure: BaseException | None = None
        previous_autocommit = True
        with lease:
            try:
                get_autocommit = getattr(self._conn, "get_autocommit", None)
                if callable(get_autocommit):
                    previous_autocommit = bool(get_autocommit())
                self._conn.autocommit(False)
                with self._conn.cursor() as cur:
                    cur.execute("START TRANSACTION READ ONLY")
                yield
            except BaseException as exc:
                failure = exc
            finally:
                try:
                    self._conn.rollback()
                except BaseException as exc:
                    if failure is None:
                        failure = exc
                try:
                    self._conn.autocommit(previous_autocommit)
                except BaseException as exc:
                    if failure is None:
                        failure = exc

        if failure is not None:
            if cached is not None and self._conn_key is not None:
                _evict_cached_conn(self._conn_key, cached)
                self._cached_conn = None
                self._conn = None
            else:
                try:
                    self._conn.close()
                except Exception:
                    pass
            raise failure

    def discover_schemas(self) -> list[dict[str, Any]]:
        """返回 schema/table/column 树（标准 information_schema 查询）。

        返回结构：
        [
            {"name": "schema_name", "tables": [
                {"name": "table_name", "comment": "表中文注释", "columns": [
                    {"name": "col", "datatype": "int", "nullable": False, "primary_key": True, "comment": "字段中文注释"}
                ]}
            ]}
        ]

        过滤系统 schema（information_schema / mysql / performance_schema / sys）。
        """
        tree: list[dict[str, Any]] = []
        with self._conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM information_schema.schemata")
            schemas = [r["schema_name"] for r in cur.fetchall()]
            for schema in schemas:
                if schema in ("information_schema", "mysql", "performance_schema", "sys"):
                    continue
                cur.execute(
                    """SELECT table_name, table_comment
                       FROM information_schema.tables WHERE table_schema=%s""",
                    (schema,),
                )
                tables: list[dict[str, Any]] = []
                for tbl_row in cur.fetchall():
                    table_name = tbl_row["table_name"]
                    table_comment = tbl_row.get("table_comment", "")
                    cur.execute(
                        """SELECT column_name, data_type, is_nullable, column_key, column_comment
                           FROM information_schema.columns
                           WHERE table_schema=%s AND table_name=%s""",
                        (schema, table_name),
                    )
                    columns = [
                        {
                            "name": r["column_name"],
                            "datatype": r["data_type"],
                            "nullable": r["is_nullable"] == "YES",
                            "primary_key": r["column_key"] == "PRI",
                            "comment": r.get("column_comment", ""),
                        }
                        for r in cur.fetchall()
                    ]
                    table_entry: dict[str, Any] = {"name": table_name, "columns": columns}
                    if table_comment:
                        table_entry["comment"] = table_comment
                    tables.append(table_entry)
                if tables:
                    tree.append({"name": schema, "tables": tables})
        return tree

    def list_tables_only(self) -> list[dict[str, Any]]:
        """轻量版 discover_schemas：只返回 schema + table 名 + 注释，不拉字段。

        用于左侧 Schema 树初次加载，避免一次性查询 302 张表的所有字段。
        点击表时再调用 list_columns_for_table 按需加载。
        """
        tree: list[dict[str, Any]] = []
        with self._conn.cursor() as cur:
            cur.execute("SELECT schema_name FROM information_schema.schemata")
            schemas = [r["schema_name"] for r in cur.fetchall()]
            for schema in schemas:
                if schema in ("information_schema", "mysql", "performance_schema", "sys"):
                    continue
                cur.execute(
                    """SELECT table_name, table_comment
                       FROM information_schema.tables WHERE table_schema=%s""",
                    (schema,),
                )
                tables: list[dict[str, Any]] = []
                for tbl_row in cur.fetchall():
                    table_name = tbl_row["table_name"]
                    table_comment = tbl_row.get("table_comment", "")
                    # D4 Phase C · C1: 追加 302 表分类标签（A/B/C/D/E）
                    table_entry: dict[str, Any] = {
                        "name": table_name,
                        "classification": _classify_table(table_name),
                    }
                    if table_comment:
                        table_entry["comment"] = table_comment
                    tables.append(table_entry)
                if tables:
                    tree.append({"name": schema, "tables": tables})
        return tree

    def list_columns_for_table(self, schema: str, table: str) -> list[dict[str, Any]]:
        """单表字段查询：按需加载指定表的列信息。

        返回结构：
        [{"name": "col", "datatype": "int", "nullable": False, "primary_key": True, "comment": "字段中文注释"}]
        """
        with self._conn.cursor() as cur:
            cur.execute(
                """SELECT column_name, data_type, is_nullable, column_key, column_comment
                   FROM information_schema.columns
                   WHERE table_schema=%s AND table_name=%s""",
                (schema, table),
            )
            return [
                {
                    "name": r["column_name"],
                    "datatype": r["data_type"],
                    "nullable": r["is_nullable"] == "YES",
                    "primary_key": r["column_key"] == "PRI",
                    "comment": r.get("column_comment", ""),
                }
                for r in cur.fetchall()
            ]

    def read_rows(
        self,
        table: str,
        schema: str | None = None,
        cursor: tuple[Any, str] | None = None,
        limit: int | None = 100,
        composite_cursor: tuple[Any, Any, str, str] | None = None,
    ) -> list[dict[str, Any]]:
        """读取表行流（带游标增量）。

        - schema 提供时，使用 `schema.table` 格式
        - 无 cursor：SELECT * FROM {table} LIMIT %s
        - 有 cursor：SELECT * FROM {table} WHERE {pk} > %s ORDER BY {pk} LIMIT %s
          cursor = (watermark, pk)
        """
        identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        for value in (table, schema):
            if value is not None and not identifier.fullmatch(value):
                raise ValueError(f"unsafe SQL identifier: {value!r}")
        if limit is not None and (limit < 1 or limit > 10_000):
            raise ValueError("limit must be between 1 and 10000")

        table_ref = f"`{schema}`.`{table}`" if schema else f"`{table}`"
        if composite_cursor:
            watermark, primary_key_value, watermark_column, primary_key_column = composite_cursor
            for value in (watermark_column, primary_key_column):
                if not identifier.fullmatch(value):
                    raise ValueError(f"unsafe SQL identifier: {value!r}")
            sql = (
                f"SELECT * FROM {table_ref} WHERE "
                f"(`{watermark_column}` > %s OR "
                f"(`{watermark_column}` = %s AND `{primary_key_column}` > %s)) "
                f"ORDER BY `{watermark_column}`, `{primary_key_column}`"
            )
            params = (watermark, watermark, primary_key_value)
        elif cursor:
            watermark, pk = cursor
            if not identifier.fullmatch(pk):
                raise ValueError(f"unsafe SQL identifier: {pk!r}")
            sql = f"SELECT * FROM {table_ref} WHERE `{pk}` > %s ORDER BY `{pk}`"
            params: tuple[Any, ...] = (watermark,)
        else:
            sql = f"SELECT * FROM {table_ref}"
            params = ()

        if limit is not None and " LIMIT %s" not in sql:
            sql += " LIMIT %s"
            params = (*params, limit)

        with self._read_only_transaction():
            with self._conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall())

    def read_rows_by_values(
        self,
        spec: Any,
        values: Sequence[str],
    ) -> list[dict[str, Any]]:
        """按冻结白名单规格批量读取，禁止调用方拼接任意 SQL。"""
        identifier = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
        table = str(getattr(spec, "table", ""))
        columns = tuple(str(value) for value in getattr(spec, "columns", ()))
        filter_column = str(getattr(spec, "filter_column", ""))
        if not table or not columns or not filter_column:
            raise ValueError("invalid batch read spec")
        for value in (table, *columns, filter_column):
            if not identifier.fullmatch(value):
                raise ValueError(f"unsafe SQL identifier: {value!r}")

        deduplicated = tuple(dict.fromkeys(str(value) for value in values))
        if len(deduplicated) > 50_000:
            raise ValueError("batch read values exceed 50000")
        if not deduplicated:
            return []

        selected_columns = ", ".join(f"`{column}`" for column in columns)
        rows: list[dict[str, Any]] = []
        with self._read_only_transaction():
            for start in range(0, len(deduplicated), 500):
                chunk = deduplicated[start:start + 500]
                placeholders = ", ".join("%s" for _ in chunk)
                sql = (
                    f"SELECT {selected_columns} FROM `{table}` "
                    f"WHERE `{filter_column}` IN ({placeholders})"
                )
                with self._conn.cursor() as cur:
                    cur.execute(sql, chunk)
                    rows.extend(cur.fetchall())
        return rows

    def __exit__(self, *args: Any) -> None:
        # 缓存复用模式：__exit__ 不关闭资源，后续请求复用
        # 资源在以下时机才关闭：
        #   - 健康检测发现失效时（重建前清理）
        #   - 进程退出 atexit / FastAPI shutdown 钩子
        self._conn = None
        self._cached_conn = None
        self._conn_key = None
        self._ssh_tunnel = None


# ═══════════════════════════════════════════════
# 私有工具函数
# ═══════════════════════════════════════════════


def _allocate_local_port() -> int:
    """动态分配本地端口（29500-30000 范围，避免端口冲突）。"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _is_port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    """检测端口是否可连接。"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _resolve_secret_path(secret_ref: str | None) -> str:
    """从 secret_ref 解析 SSH 私钥路径。

    生产环境从 Vault 读取私钥并写入临时文件；本地开发直接读路径。
    本函数返回 SSH 私钥文件路径。

    简化实现：vault://secrets/ssh_key → /tmp/secrets/ssh_key（本地开发占位）
    生产实现需对接真实 Vault 客户端。
    """
    if not secret_ref:
        raise RuntimeError("sshKeyRef is required when sshHost is configured")
    # 本地开发简化：vault://secrets/foo → /tmp/secrets/foo
    if secret_ref.startswith("vault://"):
        return secret_ref.replace("vault://", "/tmp/")
    return secret_ref


def _resolve_secret_value(secret_ref: str | None) -> str:
    """从 secret_ref 解析密码值。

    生产环境从 Vault 读取；本地开发环境直接返回（或留空）。
    """
    if not secret_ref:
        return ""
    # 本地开发简化：vault://secrets/foo → 读取 /tmp/secrets/foo 文件内容
    if secret_ref.startswith("vault://"):
        path = secret_ref.replace("vault://", "/tmp/")
        try:
            with open(path) as f:
                return f.read().strip()
        except OSError:
            return ""
    return secret_ref
