# 分析来源材料组装验证

2026-09-11；A0V-ANALYSIS-SOURCE-MATERIAL-20260911；基线b034957f。

新增同事务read_analysis_bundle与严格Bundle/grant DTO。当前Bundle exact、租户、冻结/完整/新鲜/撤销/cutoff，当前Brief exact及task归属先核验；所有Evidence r1和同Task/source/L3原授权一一完整匹配，再按Bundle顺序调用既有受控原文Owner。原文权限、Receipt、actor、当前撤销与到期和正文hash均沿原实现。超过显式byte预算拒绝，不截断或返回部分材料。

先执行测试时新模块缺失；实现后19专项通过。与分析结果解析、原文读取、直接撤销和正文完整性累计93 passed、7既有警告，退出0，1.15秒。包含一次性完整PG真实Task/Run/Brief/Evidence/Bundle/Disclosure Receipt前置图，成功读取合成指标样本，底层撤销后拒绝。测试数据仅一次性克隆，finally删除，不是栖月汇业务证据。

单元负例覆盖tenant/hash/Bundle revoked/coverage/超龄/未来cutoff、跨Task/Brief hash/未冻结、授权缺项/重复/跨Task/错误purpose或level/未知Evidence、超限与原Owner拒绝。所有前置不匹配均在正文读取前拒绝；合法输出以Bundle顺序组织，与输入grant顺序无关。

git diff --check通过；产品代码全新增，无存量API/UI/数据库schema变更，无主库写入或Provider调用。已有JDBC退出closed-stream日志错误未改，退出码0。API未重载。

边界：这是读取时的权限快照，返回材料不构成Provider出境或后续持续授权；调用前仍须当前配置/权限/预算复验。正文不得写通用日志、任务metadata或共享记忆。真实指标/Method/Eval权威、固定分析请求及原attempt绑定、可信结果Owner、宿主三阶段继续待办，不能把合成测试称真实经营完成。

下一波：上述材料到固定D01/D02生成请求与原Artifact/attempt绑定；再连接正式分析产物与三阶段宿主。真实数据/安装运行就绪、自然首链、内容评审续跑、八场景和发布观察未完成。不push，230 L0挂起。
