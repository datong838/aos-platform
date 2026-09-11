# 正式指标查询证据生产验证

2026-09-11，m1基线9635082c，AOS-000573。新增aip_metric_query_evidence内部生产器，复用Metric/Query/Task/Disclosure权威；same-actor/running TaskRun/current Metric/完整原始Evidence sources r1，逐源当前L3 source授权与marking并集，无任意来源许可推断。原请求与原结果完整保留，规范hash产生稳定ID，同事务不commit；读回列/正文hash/撤销检查，原始正文总字节数及派生正文均有界。

公共披露入口仅对aip-metric-query类型增加实时来源复核；当前same tenant/actor/requestHash的允许且未过期Decision必须有正式Receipt，并由原Owner再次检查原请求、正文、撤销/许可/标记。payload仅存稳定sourceRequests，短期授权编号不影响内容身份。没有当前有效授权则阻断，不自动申请或绕过；宿主显式续授权后相同证据恢复可读。拒绝派生父源，依赖深度限一层。

## 验证

先失败测试（模块缺失），修复测试合同构造需dict而非异类ExactRef、状态实际为blocked；首次续授权查询误用created_by，按实际schema actor修复。最终131相关测试通过（新16项全部为一次性PG）；包括正式Metric/Query/Task/Disclosure生产链、幂等/并发单对象/外层回滚零记录、缺源/错actor/错scope/错误口径/current metric升级/标记/超限/不支持Dataset/unknown freshness拒绝、原源撤销传递、原授权先过期阻断及续授权恢复、续授权同Evidence ID、自动Evidence→正式Bundle→D01读取。原始count数据和Brief为合成夹具，不是实际数据源或经营结论。7条既有警告，退出0，结束时既有JDBC关闭日志流错误。

## 一致性与边界

平台模块不依赖电商领域合同、不改变旧Evidence行为、不创建新指标/查询/权限权威，不发Provider，不新建业务路由/宿主调度，不写主库。只支持Evidence来源、same actor/source用途；未支持来源必须经过正式接入，不能手工制造来源记录冒充业务验收。生产器保留Query已有事实与不确定性，不验证任意业务计算正确性，也不是完整Metric card ready或真实质量评估。

下一波补D01画像的指标质量/方法适用性输入及固定生成，随后可信Insight、工作者、三阶段宿主与真实配置；真实源SSH恢复、真实经营计划首链、八场景和持续观察仍未完成。m1串行，不push，230 L0挂起。
