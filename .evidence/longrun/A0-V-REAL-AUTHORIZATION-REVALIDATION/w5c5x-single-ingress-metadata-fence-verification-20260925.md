# W5c5x Single ingress metadata opt-in 围栏核验（2026-09-25）

方案 `dbdc7e1d` 先行、文件清单补证 `e9437668`，实现 `47ef318d`。真实 DB 仍 `a0v_092`，Host flag 未启用。

## 九步证据

1. 复习 Single `_transaction/_run_transaction`、claim/prepare、`_finish` 的跨事务 Store effect、W5c5s 同形角色探针与 W5c5w Object 边界。
2. 仅生产文件 `pipeline_controlled_snapshot_ingress.py` 增可选精确 `OptInHostLease`；测试新增 W5c5x 隔离 PG，更新 W5c5r 静态合同和 W5c5s 无构造器替身默认字段。Single Executor、Object 上层、Store 未改。
3. 默认 None 保持原路径；显式 opt-in 时租户 GUC 设置后、绑定检查和业务 body 前逐笔 guard。`_run_transaction` 经同一入口，无独立绕行。未 acquire、错 scope、错 epoch、过期 fail closed。
4. 新专项 **2 passed**：默认、有效 holder 连续三笔及 `_run_transaction`，四类拒绝；与 W5c5r 结构、W5c5s 原角色探针合跑 **7 passed**。没有真实 claim、源读或 Store effect。
5. W5c5k–x 围栏/结构组 **35 passed**。旧 Single ingress PG 套件 **12 skipped**，不能计为通过；此前主组 162 和定义合同 24 是上波历史基线，本波未重跑，不合并伪称累计全绿。旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 跨模块顺序债保留。隔离 PG 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，`BROWSER_PARTIAL`；未保存、运行或冲刷队列，临时页面/Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0，严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。上层未传 lease，`finalize_saved_dataset` Store effect 跨独立提交边界，局部 ingress guard 不等于全链路排他；不得关闭旧组或重发旧 attempt。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5y：Single Executor 和上层 Object 显式传同一 opt-in lease；继续分离审查 Store effect，不触碰真实 DB/Host。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
