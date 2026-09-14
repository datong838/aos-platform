# SC4-2 真实Context到Plan/CompilationReceipt

基线fced8b28，m1父Lease内。新增ecommerce_analysis_compilation_preparation.py，限定精确Context准备器，在其当前来源/安装/职责/技能边界内组装L2并调用原BusinessInvestigationProfileCompiler、ProductionContractStore和CompileSaga。exact resolver只接受已选引用；Case/Run/Brief/Stage/职责/Context/Skill/各阶段Logic均读取原Store，Logic发布快照校验hash；L1解析catalog，L2和SkillSet为本次派生内容。原选择Reader仍包围整段并复验，派生引用自身无授权。

实际Plan保留productionStartGateRequired，Receipt runtimeAuthorized=false。TransactionBoundConnectFactory保持唯一外层提交，回调后复验输入、Plan及Receipt。没有直接INSERT产品Plan/Receipt，没有普通create_run绕过门禁，尚未接正式START。

RED：PG准备好图/技能发布后两项因缺少模块失败。集成发现原角色fixture只有冻结标签，实际Store读到无active SkillBinding/CapabilityBinding，真实Context拒绝。新增隔离库具名职责依赖fixture，并满足last_evaluated_at/expiry数据库约束；未修改产品readiness规则。GREEN：实际Saga与Plan两项通过；追加同请求重放、跨租户/未知引用拒绝、编译后能力撤销回滚。累计PG编译/纯组装/原Saga/Context/Skill publication为37 passed（9.79s）。

边界：图、dryrun、发布、Skill Eval/发布、Task/Brief/Bundle/Context/Plan/Receipt使用真实隔离PG服务；Logic评测来源、模型route、安装/选择及能力就绪为显式fixture，不是主安装或真实模型业务成功。第一张Plan存在不等于经营建议完成；真实TaskRun/启动门仍须下一SC4-3。全事件START严格xfail保持。

AR2 ar2-7：1899模块/177分类/93迁移，全部错误为空；memoryctl GREEN AOS-000573，1100/1083/2699；git diff --check通过。不push，230 L0挂起。下一波TaskRun启动门/恢复checkpoint与sealed Host接线，之后新候选评审安装、真实首链/八场景/观察。
