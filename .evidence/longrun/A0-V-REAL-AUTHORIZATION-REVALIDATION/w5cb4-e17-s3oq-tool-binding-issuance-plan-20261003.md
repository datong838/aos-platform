# W5CB4 E17-s3o-q｜原 ToolBinding 发行前版本与来源门

日期 2026-10-03。复习 231/231-9 栖月汇首链、128 W-L20 ToolBinding、原 `AipAssigneeResolutionStore`/router/迁移/相邻测试及 s3o-p 正式身份审计。当前权威库只读；测试仅自动销毁 PG135。m1 单写、不 push、不读商城源、不碰旧12 Run 或 230 L0。

## 已核原代码事实

- `POST /v1/aip/assignee-authority/tool-bindings` 仅校验 admin/executor/aip_executor 角色；原 `upsert_tool_binding` 直接 `INSERT ... ON CONFLICT DO UPDATE`，没有 `WHERE` version CAS/同版载荷检查，也不生成写入 Receipt。`AssigneeResolutionReceipt` 在随后 `resolve` 时生成，不能当 ToolBinding 的发行来源。
- `aip13_001` 仅令 `version >=1`、状态 active/disabled、agent_instance_id 非空；`w6_001` 增数组形状。原解析 exact version 可以在写入之后挡不匹配，但同版覆写、版本倒退和直接 runtime 写仍是发行缺口。没有正式 ToolBinding issuer 身份与 ACL 当前库材料。
- 因此本波先锁住原写路径的事实与最低版本不变量；不得仅授独立 issuer 并宣称正式绑定已发行。不能用 test-only tool/agent/Capability 装作当前正式来源。

## 文件级顺序

1. 新增 `services/aos-api/tests/aip/test_e17_s3oq_tool_binding_issuance_pg.py`：只在 disposable PG，以原 Store 写一次版本1，然后以同版本不同载荷、较低版本覆盖应拒绝为断言做 RED；确认原表/后续解析在失败后不被改动。另验证同版本相同载荷的安全重放和递增版本合法更新，维持旧调用者基本行为。直接 runtime 原 ACL 宽权若纳入测试只作为已知 RED，不写真库。
2. 如不改 API 请求合同即可修复，仅在 `aip_assignee_resolution_store.py` 原事务用条件 UPSERT/返回行和冲突错误做最小 CAS；必须区分同版同载荷幂等、同版异载荷冲突、倒退拒绝、严格递增。`routers/aip_assignee_authority.py` 将该精确版本冲突映射为稳定 HTTP 409，避免服务层新拒绝被公共 500 处理；直接用真实 Store 与 Principal 测路由，不用 mock。不要把一份读取 Receipt 误称发行 Receipt；若需要来源证明，应另立签发方案和迁移门。
3. 专项/相邻 W-L20/W6-01、Plan Tool 当前撤销测试、静态与 diff 检查。隔离正反通过后再审独立 issuer 表权与原消费者；当前库角色/ACL/OIDC 迁移单独波先备份/克隆/零执行窗口。记录残余风险、精确 m1 提交与上下文/D-wave。

本波若 RED 证明需改变公共版本/Receipt 合同，先将冲突限定为 ToolBinding 发行实例并保留 RED，不未经复审大改整个 Assignee 模型。Host/worker/Provider继续关闭。
