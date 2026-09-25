# W5c6a 跨 Store effect 边界无效应合同方案（2026-09-25）

上位 W5c5r–z：group metadata 各层现在可 opt-in 同一 Host lease，但 `recover_saved_authoritative_stages`、Link/Retirement effect 和 Dataset 缓存发布涉及独立提交/进程内副作用。`EcomConsistencyStore._apply_batch` 用 SQLAlchemy 独立 `engine.begin()`，原 Store API 没有 metadata Host lease 参数。不能凭 metadata guard 宣称 Store 原子排他。真实关闭仍等严格 24h、完整 Host 拓扑与单事务 Owner 门。

## 文件级九步

1. 复习 Single、Link、Retirement、Dataset 与 Store 原提交/回执顺序；核 W5c5z lease 链路边界。
2. 本方案先提交。仅新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6a_store_effect_boundary.py` 作为无效应合同，及 verification；不改任何生产调用或 Store schema。
3. 合同固定 effect 路径：Single saved command→Store base apply→metadata readback，后续 derived metric 每条也独立 Store effect；Link preparation→Store apply→readback；Retirement preparation→Store apply→readback；Dataset receipt commit→内存 cache。标明 Store SQLAlchemy 独立事务与 receipt replay，禁止把 metadata guard 自动推论成 effect guard。
4. 无效应静态/结构专项测试，检查前后顺序、Store 原事务与回执、无 Host lease API；不能模拟真实 effect 或补写 Receipt。
5. W5c5k–z 围栏/结构累计加本波合同；旧跳过/超时债保留。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 真实门禁只读，跨库排他设计仍是下一门，不执行旧组关闭。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6b：按真实数据库同一性/连接身份核查 Store effect 可否在其自有事务内执行 Host lease fence；若不同 DB 或权限不满足，保持 no-effect 并设计 receipt-first 替代，不盲目接线。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
