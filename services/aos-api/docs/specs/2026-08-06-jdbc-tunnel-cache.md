# 规格：JdbcConnectorRuntime SSH 隧道与连接缓存（懒复用单例）

## 1. Title / Metadata

| 字段 | 值 |
|---|---|
| 标题 | JDBC 连接器 SSH 隧道与连接缓存 |
| 负责人 | @ai-agent |
| 状态 | 草稿待确认 |
| 版本 | v0.1 |
| 关联 | 数据源详情页性能优化（按需加载字段） |

---

## 2. Context（背景 / 为什么做）

### 当前痛点

每次调用 `JdbcConnectorRuntime`（无论是 schema 发现、字段查询还是 preview 采样）都会：
1. `__enter__` 建立新的 SSH 隧道（`ssh -f -L ...` 或 `ssh-askpass` 模式）
2. 建立新的 pymysql 连接
3. `__exit__` 关闭连接 + kill 隧道

**后果**：
- 用户反映"加载很慢，但命令行查数据库很快"——根因不在 SQL，在于每次都重建 SSH 隧道（约 2~5 秒/次，含 TCP 握手、SSH 握手、认证、端口转发）
- 302 张表的场景下，用户点 10 张表 = 10 次 SSH 隧道重建 = 20~50 秒浪费

### 业务需求（用户原话）

> "系统启动时 ssh 隧道连接一次，如果需要查库时就直接查了，不要重新再连 ssh。
> 如果 ssh 隧道断了也没有查库需求，就不需要重连。
> 等到需要查数据时，例如定时同步时，检测到 ssh 断了就再连一次，连上后以后多次用。
> 就连一个就先够了。"

用户补充：
> "懒加载：启动时连好一次ssh（连的是远程服务器），首次需要查库时才链接数据库查库；
> 单例（一个隧道+一个连接）：不需要连接池；
> 健康检测 + 自动重建：使用前检测隧道/连接是否存活，死了就重建；
> 断了不主动重连：仅在有新的使用请求时才检测并重建"

翻译为技术需求：
- **启动时建立 SSH 隧道**：应用启动完成后即连一次 SSH（不用等首次查库）
- **单例（一个隧道 + 一个 DB 连接）**：不需要连接池
- **DB 连接懒加载**：首次需要执行 SQL 时才建立 pymysql 连接，启动时不连 DB
- **健康检测 + 自动重建**：使用前检测隧道/连接是否存活，死了就重建
- **断了不主动重连**：仅在有新的使用请求时才检测并重建，不启动后台 keep-alive 线程

---

## 3. Functional Requirements (FR)

| 编号 | 要求 | 级别 |
|---|---|---|
| FR-1 | 新增 **全局单例 SSH 隧道缓存**：按 `(ssh_host, ssh_port, ssh_user, remote_host, remote_port, auth_mode)` 为 key 缓存已打开的隧道实例 | MUST |
| FR-2 | 新增 **全局单例 DB 连接缓存**：按 `(db_host, db_port, database, username)` 为 key 缓存已建立的 pymysql 连接 | MUST |
| FR-3a | **SSH 启动时建立**：应用启动完成（FastAPI `startup` 事件）后，立即遍历所有已注册的 JDBC SSH 数据源，为每个不同的 SSH 配置建立 1 条 SSH 隧道（存入缓存）；启动日志记录每条隧道建立结果 | MUST |
| FR-3b | **DB 懒加载**：首次调用实际 SQL 操作（`discover_schemas`/`list_tables_only`/`list_columns_for_table`/`read_rows`）时才建立 pymysql 连接并缓存；启动时不连 DB | MUST |
| FR-4 | **健康检测前置**：每次使用缓存前，检测：<br>1) SSH 隧道本地端口是否仍在 LISTEN<br>2) DB 连接（如果已建立）是否可通过 `ping()` 或轻量 `SELECT 1` 探测<br>任何一项失败 → 销毁旧资源 → 重新建立 | MUST |
| FR-5 | **不主动重建**：没有使用请求时，隧道/连接断了就断了，不启动后台线程监控/保活 | MUST |
| FR-6 | `JdbcConnectorRuntime` 的 `with` 语义保持不变：进入 `__enter__` 时获取（复用或新建），退出 `__exit__` 时**不关闭**（归还缓存） | MUST |
| FR-7 | 进程退出时（`atexit` + FastAPI `shutdown` 事件）清理所有缓存的隧道进程和 DB 连接，避免孤儿进程 | MUST |
| FR-8 | 线程安全：缓存结构加 `threading.Lock`，避免并发请求重复建隧道/连接 | MUST |
| FR-9 | **启动时找不到数据源也不阻塞启动**：如果启动时某数据源 SSH 建立失败，记录 error 日志，应用继续启动；首次查库时再次尝试 | MUST |

---

## 4. Non-Functional Requirements (NFR)

| 编号 | 要求 | 阈值 |
|---|---|---|
| NFR-1 | 首次 SSH 隧道建立耗时 | ≤ 5s（含 SSH 握手 + 认证 + 端口转发就绪探测） |
| NFR-2 | 复用缓存的请求开销（健康检测+获取） | ≤ 50ms（TCP ping + SELECT 1） |
| NFR-3 | 隧道损坏 → 重建耗时 | 同 NFR-1，且错误日志中记录"重建原因" |
| NFR-4 | 无内存泄漏 | 缓存 key 数量 ≤ 数据源总数（不会无限增长） |
| NFR-5 | 并发安全 | 同一 key 的并发建隧道请求被 serialize，只会实际建一次 |

---

## 5. Acceptance Criteria (AC) — Given/When/Then

每条 AC 追溯到对应 FR。

### AC-1a（FR-3a）启动时即建立 SSH 隧道

> **Given** 进程启动，配置中存在 2 个 JDBC SSH 数据源（相同 SSH 配置，不同 database）
> **When** FastAPI `startup` 事件触发
> **Then** 实际只建立 1 条 SSH 隧道（按 SSH 配置去重）；启动日志输出 `tunnel_created_at_startup`；DB 连接此时未建立

### AC-1b（FR-3b）首次查库才建立 DB 连接

> **Given** 进程已启动，SSH 隧道就绪，但 DB 缓存为空
> **When** 第一次调用 `with JdbcConnectorRuntime(props) as rt:` 并执行 `rt.list_tables_only()`
> **Then** 建立 1 条 pymysql 连接并缓存；不新建 SSH 隧道；日志记录 `db_conn_created_lazy`

### AC-2（FR-1、FR-2、FR-6）第二次使用全复用

> **Given** 缓存中已有同 key 的隧道+连接（均健康）
> **When** 第二次调用同 props 的 `with JdbcConnectorRuntime`
> **Then** 直接返回缓存；不创建新 ssh 进程、不新建 DB 连接；日志记录 `tunnel_reused` + `db_conn_reused`

### AC-3（FR-4、FR-5）隧道断开自动重建

> **Given** 缓存中有隧道+连接，但 SSH 隧道进程已死（本地端口无 LISTEN）
> **When** 再次调用 `with JdbcConnectorRuntime`
> **Then** 检测失败 → 销毁旧资源 → 建立新隧道+新连接 → 正常返回；日志记录 `tunnel_rebuilt` 及原因

### AC-4（FR-4）DB 连接断开自动重建

> **Given** 缓存中有隧道+连接，但 DB 连接已超时（ping 失败）
> **When** 再次调用 `with JdbcConnectorRuntime`
> **Then** 只重建 DB 连接，保留 SSH 隧道；日志记录 `db_conn_rebuilt`

### AC-5（FR-7）进程退出无孤儿

> **Given** 缓存中有 3 条隧道、5 条连接
> **When** 进程退出（SIGTERM / FastAPI shutdown / 正常结束）
> **Then** atexit + shutdown 钩子被触发 → 所有 DB 连接被 close → 所有 ssh 进程被 kill → 本地端口被释放

### AC-6（FR-8）并发同 key 只建一次

> **Given** 10 个并发请求同时访问同 key，缓存为空
> **When** 全部请求同时进入 `__enter__`
> **Then** Lock 保证只有 1 个实际建隧道+建连接；其余 9 个等待后直接复用；最终 ssh 进程数 = 1

### AC-7（FR-9）启动时失败不阻塞

> **Given** 启动时某数据源 SSH 配置错误（密码错）
> **When** FastAPI `startup` 触发
> **Then** 记录 error 日志；应用继续启动完成（HTTP 200 /v1/health）；后续首次查库时再次尝试建立

---

## 6. Edge Cases（边界场景）

| 场景 | 处理方式 |
|---|---|
| 不同数据源但相同 SSH 配置（key 相同） | 复用同一条 SSH 隧道，DB 连接按 database 区分 |
| SSH 隧道进程被外部 kill（如 OOM） | 下次使用时检测到端口无 LISTEN → 重建 |
| DB `wait_timeout` 关闭连接 | 下次 ping 失败 → 重建连接（保留隧道） |
| 旧隧道的本地端口被其它进程占用 | 记录冲突日志 → 分配新端口 → 建立新隧道 |
| `SshTunnel.open()` 中途失败（密码错/超时） | 不写入缓存 → 抛异常 → 下次请求再次尝试 |
| 连接缓存 key 数量超过上限（如 >100） | 记录告警日志（但仍允许，不做 LRU 淘汰；数据源总数不会大） |

---

## 7. API Contracts

### 外部 API：不变

- `JdbcConnectorRuntime(props)` 构造函数签名不变
- `with JdbcConnectorRuntime(props) as rt:` 使用方式不变
- `rt.discover_schemas()` / `rt.list_tables_only()` / `rt.list_columns_for_table()` / `rt.read_rows()` 签名不变

### 内部新增（模块级私有）

```python
# 单例缓存结构
_TUNNEL_CACHE: dict[str, _CachedTunnel] = {}   # key -> (隧道实例, 本地端口)
_CONN_CACHE: dict[str, pymysql.Connection] = {} # key -> DB 连接
_CACHE_LOCK = threading.Lock()

def _tunnel_cache_key(props: dict) -> str: ...
def _conn_cache_key(props: dict) -> str: ...
def _get_or_create_tunnel(props: dict) -> int: ...  # 返回本地端口
def _get_or_create_conn(props: dict, host: str, port: int) -> pymysql.Connection: ...
def _is_tunnel_alive(local_port: int) -> bool: ...
def _is_conn_alive(conn: pymysql.Connection) -> bool: ...
def _cleanup_all_cached() -> None: ...  # atexit 钩子
```

---

## 8. Data Models

### `_CachedTunnel`（内部 dataclass）

| 字段 | 类型 | 说明 |
|---|---|---|
| tunnel | SshTunnel | 隧道实例，用于 close/kill |
| local_port | int | 实际监听的本地端口 |
| created_at | float | 创建时间戳，用于日志排查 |
| ssh_pid | int \| None | ssh 子进程 PID（用于 atexit 清理） |

---

## 9. Out of Scope（明确不做）

- ❌ **连接池**：用户明确"就连一个就先够了"，不做多连接并发池
- ❌ **后台保活线程**：不启动 keep-alive 线程；只在使用时检测
- ❌ **LRU 淘汰**：数据源数量有限，不需要淘汰策略
- ❌ **跨进程共享**：多 worker（gunicorn）场景下，每个进程独立缓存（符合"单进程单例"语义）
- ❌ **读写分离/读写负载均衡**：不在本次范围

---

## 风险与权衡

| 风险 | 缓解 |
|---|---|
| 长连接长时间闲置后，DB 端 `wait_timeout` 关闭 | 使用前 `ping()` 自动重建（FR-4） |
| 隧道长时间闲置，SSH 服务端因 ClientAliveInterval 断开 | 使用前端口 LISTEN 检测 → 自动重建（FR-4） |
| 缓存被多线程并发修改 | `_CACHE_LOCK` 全局锁（FR-8） |
| 进程崩溃时 atexit 不执行，遗留孤儿 ssh 进程 | ssh 进程用 `ssh -f`  detach 到 init → 下次建隧道时发现端口占用 → kill 旧 PID 后重试 |
| 单例连接导致并发串行（性能瓶颈） | 用户明确"就连一个先够了"；如果后续遇到瓶颈再加连接池 |
