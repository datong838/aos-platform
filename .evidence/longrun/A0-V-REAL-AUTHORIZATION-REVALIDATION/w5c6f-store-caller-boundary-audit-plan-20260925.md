# W5c6f Store caller 边界无效应审计方案（2026-09-25）

上位 W5c6a–e：Store 四条 effect API 虽已默认关闭地提供同事务 opt-in，真实库仍缺 `a0v_094`，上层未传 lease。`ec_ingress_recovery` 在短 metadata transaction 外分别提交 base/derived；Link/Retirement 在 preparation commit 后独立提交 Store，再做 readback/projection。不能把 metadata opt-in 自动推断成 Store opt-in。

## 文件级九步

1. 复习 O1 canonical Receipt/Outbox、W5c6a–e 和 Single/Link/Retirement 事务边界及 `deadline/cancel_event` 语义。
2. 本方案先提交。本波只新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6f_store_caller_boundary.py` 静态无效应合同与 verification；不改生产 caller/Store、真实 DB/Host。
3. 合同锁定 Single base、Single derived、Link、Retirement 四个 Store effect 调用仍不传 `host_lease`；各自先有持久化 preparation/readback，Store effect 独立提交，后续再核原 command。
4. 审计 deadline/cancel 边界与多 derived 独立 receipt：在 caller opt-in 之前必须证明 lease 可在每个独立事务全过程有效，失权后只读对账而非换 key 重发。
5. 专项静态测试加 W5c5k–z/W5c6a–f 累计回归；不写 Store 行。旧 skips/timeout 如实保留。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 真实门禁只读；复核 W5c6e 的续租锁竞争/长事务可用性与未接 caller 现状，不授权真实 Store effect。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6g：先设计 bounded Store transaction timeout/lease 续租兼容与提交边界，再决定是否在隔离 PG 对 caller 传 lease；若不能给出安全边界则保持 no-effect。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
