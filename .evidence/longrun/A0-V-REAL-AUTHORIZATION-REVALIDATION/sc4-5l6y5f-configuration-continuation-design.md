# Y5f 同安装同代次配置更新后的分发接续

2026-09-16，m1 19ac6e82。产品依据：真实可配置/可禁入/可恢复，栖月汇双侧增长方案禁止绕过Proposal/Approval/Lease/Receipt；AR2原路由/租户/单写者不变。不是230L0插件装载实现，也不自动开展客户触达。

## 问题与范围

J在原配置下十个exclusive operation已resumed。配置更新需原configure围栏/排空/commit后enable，epoch增长，原dispatch仍固定旧epoch，原cutover不接受extension→extension。现有successor注册要求不同已退役前驱，不能作为同安装续期。新增显式受审批的configuration refresh；保留原activation历史，不改旧receipt、不模拟legacy、不释放PreparedJob，不自动恢复旧BusinessRun。

## F1 合同（本波）

新增 services/aos-api/aos_api/ecommerce_dispatch_configuration_contracts.py 与 services/aos-api/tests/test_ecommerce_dispatch_configuration_contracts.py。严格冻结请求包含tenant、installation exact ref、generation、group和expected group revision、原resume或前次refresh exact receipt、旧binding revision/epoch/configRef、新binding revision/epoch/configRef、原configure和enable operation id+terminal revision、完整排序operation tuple、exact ActionApprovalEvent、idempotency key。新旧config为同一configuration family的后继，epoch/runtime revision严格增长；operation ids完整且只出现一次；generation与installation只有单一字段，禁止跨安装“迁移”。externalEffectsAllowed=false、resumeBusinessRuns=false，不允许携带ready/drained/authorized等客户端成功断言。

请求hash使用原canonical_sha256；approval_intent剥离approvalRef，仍包含完整scope/target、原/新authority和幂等键。这只是待验证输入，不产生执行许可、回执或DB写入。原始JSON严格解析，拒绝bool/字符串数字版本、非canonical UUID、错Ref kind、占位hash、不完整集合、同版本/跨配置family及扩展字段。审批Ref只有语法检查；当前有效性必须后续原Owner执行。

## F2 数据库与Owner（后续独立波）

先确认当前alembic head066与迁移lease，补067不可变refresh receipt链/唯一请求键/prev ref和租户隔离；仅固定非特权维护角色可经原受保护函数写。事务锁顺序沿原cutover group→installation→generation，重新读原activation/最新refresh、完整当前dispatch、当前binding、原configuration链、configure/enable request和终态event证据。验证全部同scope/installation/generation，原configure从旧config/binding进入并commit新config，新enable精确该config/代次；不信任客户端operation id、revision或hash。

原当前控制角色/markings、签名release/安装lock、新配置四源与审批时效全部重验。必须无active/unknown dispatch invocation与execution attempt，原业务Run若未终态必须明确保留且不得在本操作恢复；必要时Z正式停领/排空先行。一次事务更新全operation的epoch/group revision并插入回执；原历史不改。提交不明走原键读回，禁止新键重试。

## F3 当前权威消费（后续独立波）

原路由/disable/detach/retirement读取“原激活+配置refresh链”的current authority；不能只改dispatch表而让退役检查仍固定旧group revision。所有历史Case/Run/Occurrence仍引用原事实。未对账未知结果不续跑，不重投旧outbox。前端配置完成后需展示是否已接续、明确停用/禁入原因与待办。

## F4 验收与真实部署

真实PG负例：跨租户/旧approval/过期策略/部分operations/错前驱/不同generation/伪configure或enable/未终态/未知invocation/锁竞争/中途回滚/commit ack丢失；正例同原资源的新config接续、重放零更新，再disable/detach可用。克隆主库演练整个链，再主库正式renew→原configuration→受控refresh，随后恢复Y5d/Y6d。当前Y5e候选过期则新证据与新候选，不改旧候选日期。

## 总清单关联

Y5d十二路审批/定义、Y6d完整源组、Z旧任务恢复、真实自然经营链和八工作台持续观察全部保留未完成。F1仅输入合同，绝非维护功能完成。后续迁移/Owner/API/UI具体文件须在开工前追加，未落实施方案不隐式执行。

## F1 第5/6 验证与复核

新增合同与原cutover action/registration合同累计37 passed /3.43s。初始RED为缺模块；首次GREEN尝试发现通用ExactRef序列化含receiptId:null，显式wire(exclude_none=True)统一请求hash/approval intent，拒绝非空receiptId捷径仍由原PipelineExactRef保证。未接API/数据库/执行器，主库配置未动。

生命周期复核细节：原EcommerceGrowthDisableDependent以唯一resumed activation定位同代次，fenced_snapshot取实时dispatch而非静态旧snapshot；a0v055已经允许fence epoch大于旧activation并扩大部分排空SQL。后续不能笼统重写此Owner，须以实际最新函数为准。Python _unknown_attempts目前只取原activation epoch，refresh后必须覆盖该代次所有历史epoch并保留原unknown事实；受保护SQL的claim gate revision与原snapshot检查要针对刷新链验证。F2将先原库克隆/真实PG复核这些点，再定最小修改。

F1第6/6：仅请求合同完成。下一波F2先落当前权威读取与不可变refresh回执存储方案（具体067文件和测试清单），不开放写dispatch入口；后续F3才接原子Owner与审批/生命周期，F4隔离全链+克隆。Y5e候选仍未发布，Y5d/源组/原业务链未完成。
