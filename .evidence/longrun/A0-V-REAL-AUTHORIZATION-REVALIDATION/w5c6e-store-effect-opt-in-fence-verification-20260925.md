# W5c6e Store effect 默认关闭围栏核验（2026-09-25）

方案 `f6c2b366` 先行、历史合同文件增补 `06c65e4a`，代码/测试 `017246b1`。真实 DB/Host、上层 caller 和 Store schema 未改。

## 九步证据

1. 复习 O1 canonical Store 单事务 Receipt/Outbox、W5c6a–d、四条 effect API 和 base/derived replay/新写出口。
2. 文件级变更只含 `ecom_consistency_store.py`、W5c6a/d 两个旧静态合同、W5c6e 隔离 PG 测试和本 verification；不碰真实迁移/caller。
3. 四条 effect API 增显式 keyword-only `OptInHostLease | None`，默认 None 不执行围栏；精确类型/同 tenant scope 在开事务前验证。薄适配器在 Store 原 SQLAlchemy 事务中调用 `a0v_094`，无第二连接 guard。
4. `_apply_transaction_scope` 后首个业务写前，以及 base/derived 的 replay/new-write 每个返回前都复核。隔离 PG **5 passed**：无 holder、有效新写/replay、epoch 失权、第二 guard 失败回滚 object/receipt、replay 出口失权、scope 错误、续租锁竞争及 DB clock 到期拒绝。首次运行缺少 imported fixture，补正后通过；未在真实库运行。
5. 旧 Store/default-off 与 W5c6a/d 合计 **70 passed**；W5c5k–z 加 W5c6a–e 累计 **55 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行、冲刷队列，页面/Vite 已关闭。
7. 同事务 `FOR SHARE` 会阻塞 lease renew；长 Store 事务跨 TTL 时第二 guard fail closed 并回滚，不保证可用性。guard 与实际 commit 间仍存在极短时间边界，故不能宣称完整跨提交排他。真实库仍缺 `a0v_094`、caller 未传 lease，本波不是 Store effect 授权。实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6f：先方案和无效应合同审计 Single/Link/Retirement 上层 Store 调用点；在锁竞争/事务时长边界得到足够控制前，不接真实 caller，不迁移真实 DB。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
