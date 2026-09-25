# W5c8a Analysis Outbox 严格领取与歧义冻结验证

## 结论与范围

本波在代码和隔离 PG 中修复 Analysis DataRequirement worker 的**自动重领/自动重入入口**：新 `a0v_095` SQL 仅原子领取 `pending`；应用先只读发现 `unknown` 或过期 `claimed` 并冻结返回，不再自动调用 coordinator。旧通用 `claim_biw2_004` 保留兼容，其历史过期重领语义未改；W5c7z 负例仍是旧路径风险对照。该修复牺牲歧义项的自动恢复，后继须以原 attempt/双 Receipt 的独立只读对账设计恢复；不声称所有 Store/Host 多事务路径已安全。

代码只写仓库，未对真实 DB 应用 `a0v_095`、未重启真实 8080/worker、未变更 A0-V rev4 停用状态；因此本波是工程验证，不是实运行业务授权。

## 九步与证据

1. 复习 231、A0-V、W5c7y/z 审计、当前 m1/AOS-000662 与旧 SQL/worker。真实旧 group 仍 no authority。
2. 方案 `d2e32249` 先提交；随后 worker 单测先改并得到预期 red：6 failed/4 passed，因生产代码尚无 `read_ambiguous_next`（首次测试环境 PG 未启动的 10 个 setup error 另列，启动隔离 PG 后才得到有效 red）。
3. 最小代码 `fffcf527`：新增 `a0v_095_analysis_outbox_strict_pending_claim.py`，DataRequirementOutboxStore 严格领取/歧义只读方法，worker 只用新方法并冻结歧义；原通用领取函数及数据库数据不改。迁移降级专项补证 `643ce3a7`。
4. 新 PG + worker 12 passed；新/旧 Outbox + worker 相关专项 22 passed、7 warnings（28.58 秒）。PG 覆盖 pending 正常领取、过期 claimed/unknown 不被新函数重领、跨租户零 canary、runtime 直写拒绝；迁移 downgrade 删除新函数而保留旧函数，2 passed（15.92 秒）。
5. 近期 A0-V 短累计含两个新 PG 文件 242 passed、7 warnings（33.05 秒）；W5c7y Coordinator PG fixture 三红项仍未修复且不在本波累计选择集，不称全仓 GREEN。
6. 内置浏览器 2026-09-25 19:15:52 CST 只读回读 A0-V rev4“已配置·已停用”和“数据组已停用”；待同步写队列 1 未冲刷。
7. 双向复审：新 SQL `FOR UPDATE OF d SKIP LOCKED` 下只选 `d.state='pending'`，数据库原子阻断 expired claimed 再领；应用层歧义先读用于可观测/阻塞新工作，不单独冒充原子防重。旧函数兼容，隔离 `aos_test_*` 库清理 0。恢复路径尚未实现，真实环境未迁移/未重启；这些风险显式保留。
8. 本 verification 提交后更新 AOS CAS/Prime 强投影并回读；不将隔离测试或浏览器状态升级为真实 closure Receipt。
9. 自动进入 W5c8b：先方案，检验 `complete_a0v_050` 已提交但响应不明的双 Receipt 只读对账，并设计原 attempt 的冻结恢复；同时处理 Coordinator PG fixture 红项。

真实 gate 同波只读：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`；缺完整机器 Host 拓扑、Fresh Owner、独立 plan/key。24 小时严格阈值 2026-09-25 20:00:04.800482 UTC 不自动授予关闭权限。m1 单写不 push；230 L0 挂起；商城源不读；dev-org 仅隔离 canary；旧 attempt 不重发、不手工 `run_definition`。
