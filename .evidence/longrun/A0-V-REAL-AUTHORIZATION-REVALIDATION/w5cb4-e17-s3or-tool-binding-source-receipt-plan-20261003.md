# W5CB4 E17-s3o-r｜ToolBinding 发行来源与 Receipt RED

日期 2026-10-03。复习 231/231-9、128 W-L20、s3o-q 版本门、原 `AipAssigneeResolutionStore` 与路由、`aip13_001`/`w6_001`、`aip6_002` Registry Receipt。当前真库只读、Host/worker/Provider关闭，只在自动销毁 PG135 做原路径失败测试。用户授权持续开发，但正式来源不能由 test-only 夹具或直接 owner 写伪造。

## 合同冲突定位

- 原 `upsert_tool_binding` 接受任意满足形状的 tool_id/agent_instance_id/CapabilityBinding IDs，只凭 HTTP admin/executor/aip_executor 角色；当前无 ToolBinding 的正式 sourceRef、actor/批准/installation 精确输入及发行 Receipt。后续 `resolve` 的 AssigneeResolutionReceipt 证明一次候选解析，不证明那次绑定写入的来源或批准。
- `aip_agent_registry_receipt` 是现存 Registry 写入回执，但 ToolBinding 没有接它；直接插入 Receipt 也不足以给当前普通 runtime 的 ToolBinding 广写 ACL 提供可信发行身份证明。
- 只做独立 issuer 连接而不收窄正式来源与原写入口，可能把任意 ToolBinding 数据包装为“正式发行”。先保留此差距的原命令 RED，再决定最小扩展；不得在本波猜测当前正式 Tool/Capability/Agent 来源或写当前库。

## 文件级计划

1. `services/aos-api/tests/aip/test_e17_s3or_tool_binding_source_receipt_pg.py`：原路由/Store 在 disposable PG 写 test-only ToolBinding 后，检查同 tenant/binding/version 是否存在与写入同事务的发行 Receipt；预期失败，精确证明现行没有，不以解析 Receipt 代替。另读原请求的来源字段/当前写者身份与宽 ACL，记录不变量。
2. 先做方案/代码复审：若选 RegistryReceipt 复用，必须冻结 operation/idempotency/requestHash/resultRef、签发者身份、原子性、正式 Agent/Capability/Tool 来源校验与消费时当前性；新增迁移或公共协议须独立文件级清单和隔离克隆正反测。不得单靠页面角色或任意 `sourceRef` 文本放行。
3. 本波可只提交 RED 与验证文档，把待决协议限在 ToolBinding 发行；同步 AOS/Prime 与 D-wave 后立即转其他独立主线代码项。当前库 ACL/OIDC 切换、新全备与克隆演练另波。
