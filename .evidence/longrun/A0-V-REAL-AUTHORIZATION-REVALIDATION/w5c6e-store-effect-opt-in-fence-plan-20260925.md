# W5c6e Store effect 默认关闭围栏实现方案（2026-09-25）

上位：O1 canonical Store 以同一事务保存 object/link、checkpoint、receipt、outbox；W5c6a–d 证明 metadata 围栏不能替代 Store 围栏，隔离 PG 的 SQLAlchemy 读写原事务可调用 `a0v_094`，但真实库缺该函数。生产 API 只能显式 opt-in，默认保持原行为；此波不接上层 caller、不迁移真实库、不启 Host flag。

## 文件级九步

1. 复习 O1 Store/Receipt 方案、W5c6a–d 证据、`EcomConsistencyStore` 四条 effect API 与 base/derived 两个返回出口、`OptInHostLease.fence_in_transaction` 的同事务语义。
2. 本方案先提交。只改 `services/aos-api/aos_api/ecom_consistency_store.py`；更新 `services/aos-api/tests/extension_runtime/test_a0v_w5c6d_store_fence_api_design.py`；新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c6e_store_effect_opt_in_fence_pg.py` 与本波 verification。不得动 Store schema、真实迁移或 caller。
3. 四条 effect API 新增 keyword-only `host_lease: OptInHostLease | None = None`；精确类型和 command tenant scope 在开事务前验证。`None` 原路径不变；opt-in 用 SQLAlchemy 同事务薄适配器调用现有 lease fence，绝不独立连接读 holder。
4. 在 `_apply_transaction_scope` 后、首个业务写前守卫；replay 与新写每个 return 前再守卫，derived 同样覆盖。失权异常使原 `engine.begin()` 回滚，不把 replay 当成功；不加 read API 围栏。异常不吞、不重发。
5. 隔离 PG 用空范围构造合法 command，覆盖 base 新写/回放、derived 新写/回放及失权回滚；另测 `a0v_094 FOR SHARE` 与续租锁竞争、长事务到期。若夹在二次 guard 与 commit 间仍可能过期，明确限制而不宣称强原子排他。专项与 W5c5k–z/W5c6a–e 累计回归；旧 skips/timeout 如实保留。
6. 浏览器只读核 A0-V rev4 disabled，不保存/运行/冲刷队列。
7. 复审代码与方案：本波仅 Store API 默认关，真实 `a0v_094` 缺失，不能将隔离 GREEN 认作真实 effect 权限；继续只读真实关闭门禁。
8. verification 落盘提交；CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c6f：按隔离结果审计/最小传播 Store opt-in 到 Single/Link/Retirement 调用边界，先方案和无效应合同；若本波锁竞争或长事务不可接受，先冻结回设计。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
