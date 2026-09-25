# W5c6d Store 围栏 API 设计合同核验（2026-09-25）

方案 `d5a80502` 先行，无效应合同 `84b6bd73`。本波没有改生产 Store、真实 DB、Host 或 worker。

## 九步证据

1. 复习 W5c6a–c、Store 四条 effect API、base/derived 回执重放与新写返回、SQLAlchemy 原事务提交时序。
2. 文件清单仅 `services/aos-api/tests/extension_runtime/test_a0v_w5c6d_store_fence_api_design.py` 和本 verification；不接真实围栏。
3. 合同固定四条 effect API 当前均无 `host_lease` 参数；`_apply_batch` 与 derived 各有 replay/new-write 两条事务退出路径。目标是显式可选、同 scope、原事务内写前和每次返回前围栏；这是后续设计而非现状。
4. 专项静态合同 **2 passed**，不产生 Store effect。两次 guard 的续租锁竞争、长事务到期仍待隔离测试。
5. W5c5k–z 加 W5c6a–d 累计 **50 passed**。旧 Single ingress PG 12 skipped、旧 Object 2 skipped、旧 Schedule 完整套件超时、Attempt PG 17 skipped、`AOS_DATABASE_URL` 顺序债仍在；此前主组 162 与定义合同 24 是历史基线，本波未重跑。隔离 PG 已停；`git diff --check` 通过。
6. 5174 浏览器只读见 A0-V “已配置 · 已停用 · 版本 4 · 十二类来源”，判定 `BROWSER_PARTIAL`；未保存、运行或冲刷队列，页面和临时 Vite 已关闭。
7. 实时门禁 `REAL_CLOSURE_WAIT_24H_WITH_INCOMPLETE_TOPOLOGY`、`closureAuthorized=false`、12 原 Run running、stalled Receipt 0；严格资格仅在 `2026-09-25 20:00:04.800482 UTC` 后。真实 Store `a0v_094` 缺失，不能接线、迁移、关闭旧组或重发旧 attempt。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文和 Prime 独立受管记忆并读回。
9. 下一波 W5c6e：按设计先写方案，最小实现 Store effect API 默认关闭的围栏；以隔离 PG 覆盖新写、replay、失权回滚与续租锁竞争。未满足则冻结并回设计。

m1 单写不 push；商城源行不读；230 L0 挂起；dev-org 零 canary。
