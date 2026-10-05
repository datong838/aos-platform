# GT ModelEval 原动态合同输入校验修复验证

基线7188e62b/AOS-001344，Task gt-model-eval-ready-contract-20261005。本波修复正式申请输入读者，不完成executor、Model/Route质量门、b90完整三写或自然首链。

## 实际 RED 与最小实现

原seeded_approved_model_eval_request生产当前Model候选及申请上下文，在隔离PG以原_insert_eval维护注入缺Publication/Gate的frozen合同，原get_eval_contract回读frozen/BLOCKED且有blockers。调用原完整ModelEvalRequestStore.create竟然接受：1 failed/7.21s，DID NOT RAISE ModelEvalRequestBlocked，red.log。维护注入只为损坏负例，不当合法freeze。

原生产Store新增7行，在已持原contract head SHARE和exact/current/frozen/suite检查后，调用原ProductionContractStore.get_eval_contract(conn=同caller)，再次核hash/frozen/READY/no blockers。错误在申请INSERT前传播回滚，不增加执行权；不复制readiness算法、不用替代callback、不新建权限/表/迁移。专项1 passed/7.29s，申请计数不增，green.log。

## 原生产链 fixture 修订

移除Model请求夹具中固定Suite哈希、raw frozen合同。原内容治理Graph经实际EvalRunner/Judge→derive_gate/publish，为评测治理背景；原Suite register及canonical hash，原contract create/freeze，fresh原读者READY/blockers0。Model Suite未执行，Model target Gate0。

限制：Model Suite通过内容Suite复制dataset/judge/cases构成，只证明exact输入的注册/申请协议；不是适用于真实Model质量的合格评测套件。治理Graph发布门不替代Model/Route门。原模型及部分配置仍为隔离历史fixture，未宣称全部配置的自然生产链。正式executor须独立设计Model适用质量合同、精确身份/目标/Usage/成本/发送意图/unknown及执行时Publication epoch/Owner/Policy/预算/容量保护。

## 相邻与复审

五文件相邻：ModelEvalRequest PG、ModelEvalBudgetReservation PG、execution gate、authorization、原EvalRunner。首轮64 passed/1 failed/44.56s；唯一失败是旧fixture全表0断言，原治理现在确实生成记录。改为治理生产后全表增量0并保留Model目标Gate0，未降低无模型执行判据。最终65 passed/44.63s、7既有warnings，adjacent-r2.log。含正式签名费用/预算审批占额、共享桶竞争、自然到期保留、Price/Policy漂移、原Runner拒绝。两个Python文件compile和精确源码/方案diff --check通过。

独立只读route_supervisor核对7行同caller及原合同生产链，确认未授执行权；指出复制内容case不是Model质量标准，已纳入方案与本报告。申请时动态读取没有执行级Publication epoch持锁，申请/批准固定非执行，不能用本结果授权发送；后继executor必须重验。这不是独立后台模型报告/连续值班验收。

PG均使用5433自动一次性测试库；无当前真库查询/迁移/LOGIN/重启，无现实Provider/Secret读取、商城源/旧Run/manual/230L0/外部发送，无其他分支或push。仅提交精确本波文件，保护原修改。

下一：在原GT方案与独立精确Task内完成物理Provider容量共享权威及一次Intent，后续受限transport/Usage/原Report/Gate与Model→Route顺序；不可删通用Runner拒绝。b90接续Task保持ACTIVE、整体E16/E17及自然经营首链pending。
