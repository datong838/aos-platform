# Judge全原生链证据隔离复审

本轮仅修改test_model_eval_judge_authority_pg.py：显式新attempt root helper和纯默认/路径负门，原两producer/完整signed-suite输出改到显式root。未设置环境变量时仍返回原Main/Judge目录。显式proper Judge子目录全路径不许symlink或..，三个原helper逐字节一致，已存在legal输出拒绝复用。原全部既有函数AST经限定路径替换后逐项相等，无审批/原签名/撤回/currentness/预算/等锁/过期/租户矩阵变更，产品Owner未改。

RED：原源码缺隔离helper；纯默认/外部目录校验通过，另四fault modified-helper/symlink-helper/reused-attempt/traversal均拒绝，正常新root通过。第一次直接pytest因未显式选择隔离库触发默认autouse数据库fixture SETUP ERROR，纯测试主体未执行；保留本问题登记，不把失败当通过，也未重发未知业务操作。改为纯直接调用且无DB。

Native r1是runner选错旧Model node，pytest收集not found/exit4、database null、results空、旧hash不变，未开始业务主体；r1目录和结果保留。修正全新r2 runner并补精确whole-plan builder副本，未重用r1。r2使用当前ownedDesktop5441精确container/cluster、named local卷、完整最新迁移159、全新retained DB aos_test_0df487213fdb_ti4_test，原signed-rule-suite全链1PASS/7warnings64.78s。

独立SERIAL READ ONLY核四条Model/Judge原申请canonicalhash、新purpose model-judge-call独立批准actor与bindinghash；whole/deadline/budget_rollback三个原caller ABORTED，精确whole两parent均零；AgentRun/Modelcapacity/caseResult均零。全库另保留原测试自身显式COMMIT的一笔Judge budget hold，普通ModelEval hold零；不伪称全库所有预算均零。所有旧Main legal JSON和旧Judge whole/full proof逐个hash不变，实际root helper/test/Owner hash匹配r2 attempt。

此处是原完整链安全复验，不是expected/Target输出实际字节、tokenizer、Sourceactual-end、唯一Intent/joint、Provider、执行身份或质量证明；原Manifest部分Source/allocations/Intent refs仍descriptive，旧拒绝保持。浏览器不适用；Prime模型未知attempt不重发，本地复审不声称PrimePASS。Main/Judge完整Task不Delivery。

下一已登记步骤：在本安全新root上注册带真实expected Artifact hash的全新原Suite/Contract和独立Judge申请，再新增原Owner complete ordered expected-byte gate RED→实现→完整相邻/独立回读。没有expected Artifact时只允许精确None，不把空bytes、调用者摘要、任意resolver或旧quality申请当Judge授权。实际Target输出须另以原持久签名结果绑定，不能用expected替代。
