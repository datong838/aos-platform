# BG-02 控制Host组合与后继分析目标

2026-09-14，基线c2004db3。ProductEventControlHostService组合控制合同Owner、当前事件policy/Case/目录method、完整控制批准、同组analysis目标与CAS/Receipt。enable在SourceGuard内policy锁→041→当前批准→目标检查→CAS→复核；disable走无来源资格桥，当前admin/owner前后检查。binding目标固定ecommerce_growth_analysis_advance，与control同group/revision/installation/generation/epoch且未fence。未注册操作，外层LockedHostPort整组锁仍为运行前提。

后继修复：_occurrence_payload保留event scheduled_at=None，原定时格式不变，避免领取后读取None.isoformat崩溃。

RED缺模块；最终55 passed无skip，包括控制Host6项、控制批准/资格、原runtime适配器/保存Host。实际PG策略/Case/审批/绑定/Receipt组合；来源资格是具名替身，不能声称真实签名或SourceOwner验收。写后撤销reviewer成员时绑定+Receipt外层回滚、停用不调用失败source、旧enable回放仍保持disabled、目标围栏拒绝、原事件读取均通过。日志/tmp/event-control-host-{red,green,final}.log。

AR2初扫提示新Host反向调用未分类，按platform host port登记实际边界及新文件hash，旧preHash保留；复扫1877模块、167分类/93迁出，错误数组为空。diff通过。主库038/代码042，未重启/注册/实际启用。

下一波独立控制operation registry/Canonical Router/HTTP与包声明：保持原9操作factory，只有按真实Principal和PipelineFactory装配的registry附加control；新路由只在当前dispatch/签名合同就绪后可执行，不允许legacy回退。然后原批次消费者/自然Run目标handler、产品命令持久化与审批入口、新候选真实评审、首链/八场景/连续观察。
