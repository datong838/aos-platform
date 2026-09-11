# 正式开发文本模型与路由发布

基线dee07eb1。复习原exact-text-model-route-authority-plan及开发费用授权修订。仅org-org/dev-project，继续已授权本地开发。不会创建Capability/Skill绑定、AgentRun、业务计划或外部发布。

1. 从Owner读取当前Provider/Network/Quota/BudgetPolicy/RuntimePolicy，核验三历史probe；在.aos-recovery-20260910/state/a0v-formal-text-model-20260911冻结完整非秘密计划JSON（含固定createdAt与源hash，不保存凭据）。重复使用同文件，不根据新时间漂移已写对象。
2. 同一预算政策发布新revision，嵌入本次明确开发授权，window从本次开始至三证据最早时间+24h与现有政策截止的较早值，绑定Provider exact/agnes-2.5-flash。沿用真实BudgetRevision及商业unknownPrice默认block；授权专门承接deferred，不伪造金额。发布同授权active ModelPriceSnapshotRevision（数值全null），RuntimePolicy新revision绑定同一预算政策。每步Owner幂等/CAS回读，失败不直改表，未完成路由前不执行模型。
3. 固定RegisteredModel a0v-agnes-2-5-flash-readonly-dev r1，text→text/llm+chat，contextWindow沿既有8000配置上限（不是新的供应商规格声明），placeholder EvalGate仅用于candidate hash。正式Eval Dataset/Suite明确verified_prior_probe_metadata来源，三原时间保持；Runner每case重验读取器源hash及当前候选治理，Release服务从真实Report推导Gate，不能手填passed。Gate系统默认30天不代表本开发模型可运行30天，价格/预算授权到期后仍拒绝；新window会改变candidate hash。
4. Model发布后建立a0v-ecommerce-text-readonly-v1 r1，taskTypes仅chat.answer、单候选无fallback，RuntimePolicy引用新revision；路由合同评测明确为配置接受/拒绝检查，不叫真实内容质量。按生产Runner/Release推导route Gate，再Owner发布。后续analysis.summarize/content.generate需专项输入输出验证后增新版本。
5. 所有实际写入先备份；先在已创建一次性升级克隆演练本冻结计划，再在当前恢复库按相同顺序执行。当前健康已过期，最后就绪复验时按新的有记录健康请求处理，未知不得重发；不能用旧三样本刷新健康时间。
6. HTTP/API重载另做准确进程核验，保持自动调度/扩展关闭。留证/提交/接续。首链与八场景不在本波声称完成。


实现文件scripts/a0v_formal_text_model.py，使用freeze_plan与apply_plan受信函数，默认不存在自动外部调用。freeze_plan保存带hash的非秘密JSON，apply_plan接显式受信连接factory以便同计划先克隆后实际。预算/价格/策略Owner重放，正式评测先查同幂等运行及已有report；已有report经生产Release核验继续，存在运行无report则拒绝而非重造新attempt。模型Gate含数据库生成时间，克隆/实际各自产生真实Gate与最终Model hash，route从各自正式model ref构造，不能跨库移用Gate。方案与脚本的专项验证以隔离完整升级克隆执行/再执行零新增权威计数为主。

复核补充：历史探针hash相同仍不代表当前Provider/Network有效；读取证据之前核验当前Provider与Network active及Network有效期。新增services/aos-api/tests/extension_runtime/test_a0v_formal_text_model.py覆盖停用、撤销、到期、尚未生效和计划漂移拒绝。冻结计划落盘后同步父目录，避免重启丢失目录项。
