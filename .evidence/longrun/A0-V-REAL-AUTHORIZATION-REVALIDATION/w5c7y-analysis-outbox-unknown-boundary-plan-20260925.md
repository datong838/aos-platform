# W5c7y Analysis DataRequirement Outbox unknown 边界计划（no-effect）

## 上位与文件级清单

承接 W5c7v/x：三业务 worker 的多提交路径不由 Pipeline Owner fence 证明。选择 `services/aos-api/aos_api/ecommerce_analysis_data_requirement_worker.py` → `data_requirement_outbox_store.py` → `ecommerce_analysis_snapshot_coordinator.py` → `pipeline_control_service.py` 作单链分析，并复核 `services/aos-api/tests/extension_runtime/test_analysis_data_requirement_worker.py`、`test_analysis_snapshot_coordinator_pg.py`、`services/aos-api/tests/test_data_requirement_outbox_store.py`。本波仅新增 audit/verification 证据，不改生产代码；若发现可独立修复的具体缺陷，下一波另立方案。

## 九步

1. 复习 A0-V no-effect、W5c7b/v/x、当前 AOS/Prime 版本和 m1。
2. 本方案先提交，固定上述文件与判定问题：claim、协调、Outbox complete/unknown 的每个独立提交及重试资格。
3. 输出序列矩阵，特别区分 unknown 状态成功持久化、unknown 标记本身未知、已 ack 但调用方返回未知三种情况；不把 delivery lease 当 Host epoch。
4. 跑 worker/Outbox/Coordinator 原专项，记录确切通过数和不覆盖项。
5. 跑近期 A0-V 累计短回归；不把历史长例重算为本次。
6. 浏览器只读验 rev4/组停用，不冲刷写队列。
7. 与代码/SQL 合同复审；若存在未知结果自动重发可能，登记为阻断而非直接启用 Host lease。
8. verification 落盘提交 m1，CAS 更新 docs 与 Prime 三投影。
9. 自动进入 W5c7z：优先对 unknown 标记失败/ACK 结果不明的再次领取资格做隔离 PG 负例；决定最小修复前先复现。

真实 `a0v_093/094`/Host opt-in/closure 不执行，旧 attempt 不重发、不手工 run_definition；商城源行不读、230 L0 挂起、dev-org 仅隔离 canary、m1 不 push。
