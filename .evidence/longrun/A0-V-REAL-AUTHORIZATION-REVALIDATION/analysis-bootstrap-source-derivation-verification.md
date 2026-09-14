# SC4-4a 受控来源派生初始化许可

2026-09-14，基线658558da。按analysis-bootstrap-runtime-design.md修正正式接入路径：每事件额外等待人工初始化会违背自动首链，故在原事件enable独立审批当前有效、精确来源/对象均当前且没有已有评审记录时，由专用暂停门派生仅初始化许可。

ActionProposal保持drafted，不插入ActionApprovalEvent。服务端固定初始化policy显式声明controlledSourceInitialization；通用启动、普通恢复、外部租约仍不可使用。真正经营方案审批不变。若已人工拒绝/撤回、发生评审、来源失效或Action快照漂移，不能以派生许可绕过。

新增可回读analysis-initialization-authority Evidence，记录kind=current-event-control-initialization、真实executor、原ControlReceipt/Occurrence、意图/Preview/Proposal exact引用、验证时间及零业务/外部授权声明；原启动决定依赖hash包含该Evidence引用，完整证明正文保存在Evidence中。回读和撤销检查覆盖重放，不伪造人工批准。原独立审批路径继续保留并记录自己的kind。

首次派生用例红测为exact approved proposal required；实现后累计40 passed、7既有警告、27.94秒（/tmp/a0v-bootstrap-derived-final.log）。覆盖自动初始化与无人工记录、实际拒绝、父来源撤销、注册快照漂移、权威Evidence撤销、原独立审批与通用隔离。AR2 1904/182/93错误为空；memory GREEN AOS-000573。

仅隔离库，Source/角色/Action/部分依赖fixture，不是主租户授权。下一正式事件入口自动准备、同一Run稳定重放及sealed Host最后绑定；再真实续跑和主安装验收。无push，230 L0挂起。
