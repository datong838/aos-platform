# W5c7z Outbox unknown 标记失败 PG 负例验证（no-effect）

## 结论

隔离 `aos_test_*` PG 实证 W5c7y 风险：`claim` attempt1 后 `mark_unknown` 未持久化，DB 仍 `claimed`；lease 过期后原 Outbox 可被 attempt2 再领。测试不调用 coordinator/商城源，故只证明重新领取资格，不证明发生了真实源重发。`ack` 确认提交后即使调用方未收到响应，也不可再领取；这是 legacy `ack_biw2_004` 路径，非 A0-V `complete_a0v_050` 双 Receipt 正例。结论是风险已复现、尚未修复；真实 Host/worker opt-in 继续禁止。

## 九步证据

1. 复习 231、A0-V、W5c7y 审计及当前 m1/AOS-000661；真实 closure 仍 no authority。
2. 方案 `b543cf03` 先提交；锁定 Outbox SQL、worker 与新隔离 PG 测试。
3. 测试 `f81d84f2`：`services/aos-api/tests/test_a0v_w5c7z_outbox_unknown_failure_pg.py`。以错误 token 触发确定性标记拒绝，模拟未持久化，而非伪造网络提交不明；确认 DB claimed attempt1、过期后二次 claim attempt2、dev-org 无可领对象及 ACK 后不可领。
4. 新例 `1 passed, 7 warnings`（8.93 秒）；相关 worker/Outbox/新例 `20 passed, 7 warnings`（18.89 秒）。隔离测试库清理后 `aos_test_*` 数量 0。
5. 近期 A0-V 短累计含新例 `240 passed, 7 warnings`（21.89 秒）。W5c7y Coordinator PG 三例 fixture 红项不在本波累计选择集，不因此变绿；历史长例不重算。
6. 内置浏览器 2026-09-25 19:07:04 CST 只读回读 A0-V rev4“已配置·已停用”及“数据组已停用”；待同步写队列 1 未冲刷。
7. SQL `claim_biw2_004` 的过期 claimed 再领取谓词与测试一致；worker `mark_unknown` 异常仅记日志，与风险结论一致。没有修改生产代码，下一波应先决定 fail-closed 修复的事务边界及兼容影响。
8. 本 verification 提交 m1 后做 AOS CAS、Prime 强投影回读；不将 PG 负例视为真实业务 Receipt。
9. 下一波 W5c8a 先方案：阻断已可能开始执行但 unknown 标记未落库的自动再领，明确恢复/对账途径，并补 `complete_a0v_050` 已提交但响应不明的隔离证明。Coordinator PG fixture 红项仍登记。

真实 gate 同波只读回读：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`；缺完整机器 Host 拓扑、Fresh 单事务 Owner、独立 plan/key。24 小时阈值不是授权。m1 单写不 push；230 L0 挂起；商城源行不读；旧 generation 不重发、不手工 `run_definition`。
