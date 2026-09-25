# W5c6i DB Owner / Store effect 原子边界核验（2026-09-25）

方案 `54a33538` 先行、无效应合同 `49d66b50`。未改生产 closure/SQL/Store/Host/caller、真实 DB。

## 九步证据

1. 复习 `a0v_091` closure 的 maintainer/SERIALIZABLE/Receipt、`a0v_093/094`、Store base/derived 独立 Receipt/事务与上层 caller。
2. 文件级仅新增 `test_a0v_w5c6i_owner_store_atomicity_boundary.py` 与本 verification。
3. 合同证实 stalled closure 用 `consumer_connection` 和受限 maintainer 单事务、回读 closure Receipt；Store effect 另开 SQLAlchemy `engine.begin()` 并用 runtime role，公开 effect API 不接受外部 transaction connection。
4. `a0v_091` closure Receipt 只证明旧 group 终结，不写 `ecom_ingest_receipt`/`ecom_derived_receipt`，不授权原 Store effect 重发。先正式 closure 后 exact direct successor 仍须独立新波/唯一 key；合并 Owner/Store 须重设计角色、RLS、幂等、外部 effect，不可拼接。
5. 专项 **3 passed**，W5c5k–z 加 W5c6a–i 累计 **67 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。无完整 Host 拓扑/单事务 Owner 新授权，不调用 closure、不迁移真实 `a0v_093/094`。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6j：按正式 closure 前置条件设计全机 Host 拓扑只读发现器/证据；不从 UI 或单进程推断全机唯一性，真实仍 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
