# W5c8d 原 attempt 双 Receipt 纯只读 resolver 方案

## 上位、现状与禁止项

承接 231、A0-V fail-closed、W5c8a/b/c 与 AOS-000665。真实 closure `automaticAction=false`、`closureAuthorized=false`、12 原 Run running；运行中真实库未迁入 W5c8a 严格 claim。W5c8c 已审定 `_replay_committed` 会重入 `_resume`，不能作为只读恢复器。本波只对隔离 PG 的原 DataRequirement Outbox attempt 建立**只读证据解析**；它不 ACK、不标记 unknown、不重领、不调用 coordinator/source，也不为真实 A0-V 提升 authority。230 L0 挂起，商城源数据不读，dev-org 仅零 canary。

## 文件级清单与最小接口

- 新增 `services/aos-api/aos_api/ecommerce_analysis_original_attempt_receipt_resolver.py`：输入精确 `TenantScope`、持久 Outbox 原 attempt（含 requirement id/revision/hash、attempt、lease token）和连接工厂；只读核对 Outbox 行仍是同一原 tuple 且状态为 `unknown` 或过期 `claimed`。直接读持久 Analysis Receipt，不调用 `_resume` 或 `coordinator.run`。
- 最小修改 `services/aos-api/aos_api/ecommerce_analysis_snapshot_coordinator.py`：把 `_resume`/`_replay_committed` 已共用但重复书写的 canonical tenant+RequirementRef 幂等键公式抽为同文件纯函数，由新只读 resolver 复用；不改键格式或自动执行顺序。以现有 Coordinator PG 长例和新解析器隔离 PG 验证等价，避免复制哈希权威逻辑。
- 使用 `BoundEcommerceGrowthRuntimeStore.read` / `read_exact`、`DataFulfillmentStore.read_exact` 及 `a0v_050` 所需的严格字段谓词；只接受唯一 RUNNING、未完成、精确 Requirement/Run、精确 FulfillmentRef、同租户同源绑定。解析返回证据结构或显式冻结原因，不返回可写命令/授权。若现有 Store 响应不足以证明任一谓词，则 fail closed，不猜测。
- 新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c8d_original_attempt_receipt_resolver_pg.py`：复用原快照链一次性隔离 PG，验证唯一完整证据、缺 Receipt、PREPARING、错误租户/Run/Requirement、重复候选、attempt/token 漂移、过期 claimed 与 dev-org 零可见；测试连接强制只读，运行后的 source 调用计数保持 1。测试造数不得触商城源。
- 只在 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/` 新增 verification；不改 Worker 自动路径、数据库迁移或真实 DB。若最小接口证明需要新持久索引/SQL，停在设计复审并另立方案，不在本波引入状态写入。

## 九步与退出

1. 复习 231/产品、W5c8c 审计、现有 Store/SQL/测试和真实 gate，确认单写 m1。
2. 本方案先提交；核对接口输入、幂等键与双 Receipt 完整谓词。
3. 最小实现纯只读 resolver，未知或不唯一返回冻结；无生产自动接线。
4. 专项隔离 PG 正/负例及无写/无源断言。
5. 近期短累计回归；不以短测冒充长 Coordinator 链。
6. 内置浏览器只读 rev4/停用验收，不冲刷待同步队列。
7. 方案/代码/SQL 一致性、隔离与失败边界复审；任何读写混合即停。
8. verification 落盘提交，AOS CAS/Prime 强投影回读，真实 gate 复核。
9. 自动进入 W5c8e：如只读证据已被隔离 PG 证明，再**单独方案**评估持久 `unknown` 原 tuple 对账 authority；过期 `claimed` 状态迁移继续另设门禁。

m1 唯一提交者、不 push、不动其他分支；不手工 `run_definition`，不重发旧 attempt，未知边界先冻结。
