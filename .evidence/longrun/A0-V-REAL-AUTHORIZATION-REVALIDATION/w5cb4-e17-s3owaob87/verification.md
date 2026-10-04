# b87 来源许可专用身份前置验收

## 当前实证
- 身份未识别、通用编辑/producer/Store 未拒绝 RED：10 failed，5.05s，见 red.log。
- 通用执行器按身份不拒绝，即使缺策略或 executionAllowed=true：6 failed/1 passed，4.59s，见 red-execution.log。
- 首轮23 passed/4.56s，扩大相邻75 passed/28.43s，最终92 passed/66.00s（范围重叠，不相加）；包含原 guard/network 审批、执行Lease、single-attempt、unknown-result reconciliation等隔离PG测试。最终签名真实完整schema、source与Policy事实回归1 passed/15.63s。
- 八个代码/测试文件编译通过、精确diff检查通过。签名回归后测试数据库49；本轮迁移夹具产生的NOLOGIN fence owner无危险属性、双向成员0/共享依赖0后清理，最终0。未删历史49数据库。

## 实现与一致性复审
固定 aip_issue_source_license；R2下限、maker-checker，hint只能升风险。executionAllowed=false，sourceLicenseIssuanceOnly=true，专用consumer接续。原通用编辑/seed通过既有保留身份检查拒绝；服务在schema前拒，Store请求/批准按request或snapshot任一身份匹配拒；直接create在transaction前拒。执行器在租约和执行共同precheck按身份拒，独立于策略字段。原policy错误类型及普通动作不变，无新表/审批库/授权backfill、无通用callback。

## 真实限制与后续必做
这是完整发行命令的身份前置，不是合法来源许可、typed producer/checker或issuer交付。计划步骤2需原OIDC maker/current Owner与独立checker、精确source/provenance、用途和有效期、当前安装及签名Policy绑定并复用原Proposal/Approval。步骤3/4独立issuer最小权限、共同锁、原Approval精确消费、issuance/head/RegistryReceipt原子提交，随后实际PG正向、竞争与回滚验收；仍不得宣称真实自然首链。

当前135真库未迁移/重启，Host/worker/Provider/商城源/旧Run/外部效果均未执行。org-org/dev-project正向，canary无业务副作用。无页面改动，浏览器不适用。权威1329、强投影CURRENT；真实agnes r3 assessment6/7与O4限制保留，本轮未调用模型。
