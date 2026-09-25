# W5c8e unknown 原 tuple 对账 authority 审计计划

## 上位、状态和目标

承接 231、A0-V fail-closed、W5c8c/d 和 AOS-000666。W5c8d 只证明持久 `unknown`/过期 `claimed` 原 attempt 可在隔离 PG 纯只读找到双 Receipt；真实 closure 仍无 authority。本波**先审计**：`unknown` 原 tuple 若要调用既有 `data_requirement_outbox_reconcile_completed_a0v_050`，除双 Receipt 外，是否还能独立证明原 Requirement、源组、Host/Store 跨事务围栏和提交边界。不得因找到双 Receipt 即接入 Worker 或真实恢复；任何必需证据缺失，则给出精确缺口与后继最小实现方案，保持代码默认冻结。

## 文件级清单

- 读 `services/aos-api/aos_api/ecommerce_analysis_original_attempt_receipt_resolver.py`、`ecommerce_analysis_data_requirement_route.py`、`ecommerce_analysis_data_requirement_worker.py`、`data_requirement_outbox_store.py`、`pipeline_snapshot_group_locator.py`、`ecommerce_growth_runtime_connection.py`。
- 读 `services/aos-api/alembic/versions/a0v_050_data_requirement_outbox_completion.py`、`a0v_093_host_lease_foundation.py` / `a0v_094` 实际路径，以及 W5c8d PG 证据；核既有 SQL `unknown` 状态、原 attempt/token、双 Receipt 原子谓词。
- 本波只新增同目录 audit/verification，不更改生产 Worker/SQL/真实库。若审计证明授权所需的独立路径完整，下一波才方案化隔离 PG 的显式、非自动原 tuple 对账接口；过期 `claimed` 保持另一条状态迁移门。

## 九步和停止条件

1. 复习 231、产品 A0-V 授权边界、authority/Git/真实 gate，保持 m1 单写。
2. 本方案先提交，固定 `unknown` 单状态、原 tuple、双 Receipt、源组/Host 证据的判断口径。
3. 逐字段对照只读 resolver 与 `a0v_050` SQL，画出证据来源、时间点和跨事务风险矩阵。
4. 专项检查现有路由读取是否会碰源、当前安装/Host 有效性是否可只读证明；未知即停止。
5. 跑不触源的专项与近期短累计；不以隔离 PG 替代真实授权。
6. 内置浏览器只读 rev4 停用验收，不冲刷队列。
7. 方案/代码/SQL 一致性复审；任何缺源组或 Host 围栏不得写 `reconcile_completed` 或自动恢复代码。
8. audit/verification 落盘提交，AOS CAS/Prime 回读，真实 gate 复核。
9. 自动进入 W5c8f：按审计结果选一项最小独立只读证据补齐；若全部 authority 成立，先新方案再隔离 PG 验证受控对账。过期 `claimed` 不并入。

m1 不 push、不动其他分支；230 L0 挂起、商城源行不读、dev-org 仅零 canary；旧 attempt 不重发、不手工 `run_definition`、未知提交边界先冻结。
