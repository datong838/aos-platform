# W5c7z Outbox unknown 标记失败隔离 PG 负例计划（no-effect）

## 上位与目标

承接 231 唯一总控、A0-V fail-closed 与 W5c7y 审计 `062848e3`。只在一次性 `aos_test_*` PG 库复现：已领取、协调结果不明、`mark_unknown` 未持久化、lease 过期后再次领取的真实 SQL 资格；同时核对 ACK 后响应不明时不会再次领取。证明风险，不对真实 Run/Outbox 做实验。W5c7y 的 Coordinator PG fixture `analysis snapshot group differs from original source` 红项独立定位，未修复前不能借用作本波正例。

## 文件级清单与变更

- 读：`services/aos-api/aos_api/ecommerce_analysis_data_requirement_worker.py`、`data_requirement_outbox_store.py`、`services/aos-api/alembic/versions/biw2_004_data_requirement_outbox_delivery.py`、`a0v_050_data_requirement_outbox_completion.py`；复习 W5c7y audit/verification。
- 拟新增：`services/aos-api/tests/test_a0v_w5c7z_outbox_unknown_failure_pg.py`，复用 `tests.aip._migration_test_support.isolated_aip_migration_database`，仅模拟 Outbox 的本地未提交/异常结果，不接商城源、Coordinator、真实 Host。
- 生产代码暂不修改；若证实防重缺陷，后继 W5c8a 先补独立最小修复方案和失败测试，再改实现。测试必须按现状断言真实行为，不把错误行为写成最终可接受合同。

## 九步及退出

1. 复习上位方案、m1/authority/Host/真实门禁；确认隔离 DB 与无第二写者。
2. 提交本方案，固定 SQL/测试文件与断言。
3. 新增隔离 PG 负例：claim attempt1、未知标记失败但 DB 仍 claimed、过期后二次 claim attempt2；ACK 后异常回读不再可领取。验证 dev-org 隔离只作为零 canary。
4. 跑新专项；检查一次性库清理为 0。
5. 跑受影响 Outbox/worker 专项与近期短累计；Coordinator PG 红项单列，不伪报 GREEN。
6. 内置浏览器只读复验 A0-V rev4/组停用，待同步写队列不冲刷。
7. 方案/代码/SQL 一致性复审：明确“风险已复现”与“风险已修复”不同；再读真实 gate。
8. verification 落盘提交 m1，AOS CAS 与 Prime 回读；若专项失败先定位，不把波次记完成。
9. 自动进入 W5c8a：先方案解决 unknown 提交不明防再领；或若负例未复现，先修正审计结论与门禁，不接真实 Host。

不变边界：m1 单写不 push；旧 generation 不重发、不手工 `run_definition`；真实 closure 无完整机器拓扑/Fresh Owner/独立 plan-key 不执行；230 L0 挂起、商城源行不读、dev-org 仅隔离 canary。
