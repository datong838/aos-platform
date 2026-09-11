# D03 Canonical 工作者接线方案

2026-09-11；基线2a950219，AOS-000573；m1单写、不push、230 L0挂起。

唯一存量fixture preHash：test_ecommerce_analyst_growth_plan_full_graph.py=7c2817d29de84072fe734d1c485a3cd736c68d2c7ad1a154beb406c53db6a766；其他产品代码均新增。三个阶段必须applicable，不把approved但排除执行的步骤启用。

产品目标：真实画像、诊断完成后，由指定数字同事形成有来源的经营计划草稿，写入正式Owner，检查点承接精确引用，等待后续人工评审。依231-5/231-6，本波是前序generation composition和恢复/续租的实际内部调用点，不另建调度器，不自动审批。

## 具体文件与合同
- 新增 `services/aos-api/aos_api/ecommerce_analyst_growth_plan_worker.py`：显式scoped factory、保留正文的executor、clock/markings/TTL；组合既有AipTaskStore/CanonicalTaorRunner、AgentRunService、GrowthPlanGenerationService、AnalystOwner。
- 入场只接受当前running/executing、exact已批准Plan，重算完整Plan hash；步骤顺序严格portrait、diagnosis、solution-design，前两步已成功；D03 AgentRun必须同Task/TaskRun/Plan revision且Skill D03，AgentInstance精确匹配solution-design唯一受信assignee。不可从taskGoal任选模型/角色/来源。
- 固定attemptId = growth-taor- + canonical hash(tenant、TaskRun、Plan ID/hash、solution-design)前40位；attemptNo=1。原调用未知不能通过新编号绕过。其他预算/容量/来源/版本参数仍由既有generation/executor权威验证。
- 适配器think核对恢复后的portrait.insightRef与diagnosis.decisionRef和真实当前Decision；只记录固定command hash/attempt元数据。act调用generation；任何无法证明完成的异常转为固定安全的TransitionBlocked，不能被通用runner降为可重试失败。verify回读正式draft、租户、decision、预算及内容hash；observe仅GrowthPlan exact ref和空artifacts，不复制正文/生成重复Artifact。runner显式启用续租。
- 新增 `services/aos-api/tests/test_ecommerce_analyst_growth_plan_worker.py`；必要时为既有完整隔离fixture增加显式taor_ready开关，构造三阶段完整plan并重新计算hash及固定attempt。默认fixture保持原样。通过真实PG Owner/Generation恢复/Runner检查点，禁止Provider调用；metadata合成不是实际业务。

## 退出/风险/下一步
先红后绿、串错Task/Plan/assignee/来源/attempt负例、原成功模型产物零调用恢复到正式计划与检查点、回归、证据、提交。退出不要求真实源未恢复的客户调用。真实D01/D02生成、职责/技能/能力配置、AgentRun创建调度、宿主dispatch仍待后续；本波内部入口不开放公共route。历史结果非当前授权；最终审批仍须来源重验。API未重载前不称运行环境已接通。
