# BG-02 当前控制批准与停用身份

2026-09-14，基线6fdabd94。共享当前审批实现保留schedule_put入口，新control入口固定ecommerce_growth_event_control及完整Proposal payload（caseId/schedulePolicyId/controlIntent，包含原key/expectedBindingRevision/策略ref/intent，不含approvalRef）。控制动作R2底线，复用快照、当前风险/审批policy、真实成员/marking、独立quorum和截止时间；旧保存批准不能替代控制。

停用身份入口独立检查真实runtime scope与当前meta_membership的admin/owner，不依赖来源可用性或旧批准。remote OpenFGA尚无当前适配则拒绝。没有grant、假账号、HTTP或新operation注册。

RED缺模块；最终31 passed无skip（控制批准10项、原当前批准、风险及CAS），包含正例、不同key/版本/意图拒绝、旧save批准拒绝、角色撤销/只读角色/跨tenant停用拒绝。PG是真实表，但批准及目录为具名fixture，不是真实用户审批/发布签名验收。日志/tmp/event-control-approval-{red,green,final}.log。AR2扫描1875模块、166分类/93迁出错误数组为空，diff通过。主库038/代码042，后台未重启。

下一波控制Host/当前合同资格：enable复用当前来源Owner、当前策略/Case、上述批准及绑定CAS；disable必须可在来源失效时安全停用。精确新合同/新operation注册只在完整Owner就绪后进入签名候选。产品入口/自然消费/Run承接/首链/八场景/观察均未整体完成。
