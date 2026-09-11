# D03 受信工作者验证

2026-09-11；Task A0V-D03-TAOR-WORKER-20260911；基线2a950219。

## 实现结果
新增 GrowthPlanTaorWorker，实际组合 CanonicalTaorRunner（显式续租）、已治理AgentRun、GrowthPlanGenerationService与AnalystOwner。核验已批准Plan完整hash、三阶段顺序/applicability、前两步成功、同Task/TaskRun/Plan、D03 Skill与唯一AgentInstance assignee。生成编号由tenant/TaskRun/Plan hash/步骤固定，attemptNo=1；原结果不明时固定TransitionBlocked，不转成通用失败重试。think检查原画像/诊断引用及当前来源，observe仅正式GrowthPlan exact引用，空artifacts。

## 本次验证
- 新测试先因尚无worker模块失败。首次实现后的3个真实PG场景已通过，15个单元测试因测试ResourceRef缺必填authority失败；补全测试引用后18通过，未放松产品合同。
- 补充完整hash一致的not_applicable/无指定Agent/不可信assignee来源负例；最终worker21项，累计13组229 passed、7既有警告、退出0、13.87秒。
- 3个一次性完整克隆场景：成功从原SUCCEEDED attempt及私有答复恢复草稿，真实GrowthPlan Owner回读“检查回购间隔”，draft非approved，3检查点且仅1原Artifact；终态再次调用被拒绝，无新模型调用。来源引用错误与注入无法确认结果均不产生D03 observation、只有原2检查点、Run仍running等待恢复。
- 原模型执行器是禁止调用的NoProvider守卫；其他实际Generation/Receiver/Source/Run/Artifact/Plan/Task/Lease/Checkpoint读取写入均使用真实隔离DB。前置AgentRun/来源/已批准Plan由合成fixture构造，不是真实配置批准或经营结果。默认旧fixture保持原样；只通过taor_ready显式构造新场景。
- git diff --check通过。无主库业务写入、无Provider调用、无公共route、无API重载、无push。既有JDBC退出清理日志closed-stream错误仍存在，未影响退出码。

## 限制与下一波
真实D01/D02可读分析产物、宿主调度与AgentRun创建/绑定尚未接通；不是栖月汇真实计划或全链闭环。此内部worker要求调用方持有有效markings、clock、TTL及既有预算/容量批准；不从客户端任意目标造授权。未知attempt需对账，不自动换编号。计划审批前仍待当前来源重验。

下一波：接D01/D02真实分析产物和正式AgentRun创建/职责绑定，再接宿主的三阶段执行；同步推进真实数据连接与当前安装运行就绪，随后首链自然触发、人工评审后的内容续跑和八场景。费用不作开发阻断，230 L0仍挂起。
