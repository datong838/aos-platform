# W5c8a Analysis Outbox unknown fail-closed 领取修复计划

## 上位事实与设计裁决

231 总控要求最小安全修复先方案、后测试/代码、真实门禁不越权。W5c7y/z `062848e3`/`adb94027` 已证：`mark_unknown` 失败时过期 `claimed` 可自动升 attempt2；已持久 `unknown` 分支又调用完整 coordinator，不能仅凭“reconcile”名称证明无新源读取。因此本波只修 Analysis DataRequirement worker 的**自动入口**：新领取只取 `pending`，遇到既有 `unknown` 或过期 `claimed` 停在只读冻结状态，绝不自动调用 coordinator。现有通用 `claim_biw2_004` 保留兼容，新的严格 SQL 函数供该 worker 显式调用，不暗改其他消费者。这样牺牲自动崩溃恢复，后继波以原 attempt/双 Receipt 的独立只读对账再恢复，不靠新 attempt 或重新调用业务链。

这个裁决不声称完整 Host fence、Store 多事务安全、真实业务完成；也不处理旧 A0-V generation。若无法确保严格领取与歧义先读在数据库同一原子边界，SQL 必须自身排除过期 `claimed`；应用层先读只负责防未知优先级和可观测，不作为唯一互斥证据。

## 文件级清单

- 迁移新增：`services/aos-api/alembic/versions/a0v_095_analysis_outbox_strict_pending_claim.py`，基于 `biw2_004` 同租户/权限/锁契约，仅 `pending` 可由 Analysis worker 新领取；不给直接表 UPDATE 权，downgrade 只撤新函数。
- 最小代码：`services/aos-api/aos_api/data_requirement_outbox_store.py` 新增严格 pending 领取及只读歧义查询；`ecommerce_analysis_data_requirement_worker.py` 只走严格入口，并遇到歧义时返回 unknown、不调用 coordinator。
- 测试：`services/aos-api/tests/test_a0v_w5c8a_outbox_strict_claim_pg.py` 证明过期 claimed/unknown 不可由新函数再领、pending 可领、旧函数兼容、dev-org 零 canary 与 runtime 权限；更新 `test_analysis_data_requirement_worker.py` 的确定性入口/未知不重入；保留 W5c7z 旧风险复现作为迁移前/通用函数对照。不得把 Coordinator PG fixture 红项静默删除。
- 证据：本计划和同目录 verification，AOS CAS、Prime 强投影、浏览器只读。

## 九步及退出

1. 复习 231、A0-V 真实 gate、W5c7y/z 与实际 SQL/worker/test，确认 m1 单写。
2. 本方案提交；先写失败测试并记录 red。
3. 新增严格 SQL + store/worker 最小改动；不得更改通用函数语义或真实配置。
4. 专项覆盖 pending/expired claimed/unknown/acked、权限/隔离、两个 worker unknown 分支（已持久与标记失败）。
5. 近期累计短回归；另核 Coordinator PG fixture 已知红项，不以排除称全绿。
6. 内置浏览器只读确认 A0-V rev4 停用，队列不冲刷。
7. 方案/代码双向复审：严格函数数据库原子排除重领；自动 unknown 不重入 coordinator；恢复由后继独立只读对账，不误写已解决。
8. verification 落盘提交、CAS/Prime 校验；如果影响正常 pending 领取则先修复，不推进。
9. 自动进入 W5c8b：完成 A0-V `complete_a0v_050` ACK 结果不明的双 Receipt 隔离证明和原 attempt 只读恢复方案；若有缺口继续 fail closed。

边界：m1 不 push；商城源不读、旧 attempt 不重发、不手工 `run_definition`；230 L0 挂起、dev-org 仅隔离 canary；真实 closure 须完整机器 Host 拓扑、Fresh Owner、独立 plan/key 与严格时间门，均未满足。
