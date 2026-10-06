# S10 原allocation批准事实进入完整private声明消费者

基线AOS-001399 / m1@1da9eb1c；复习231及sql-approval-equivalence-plan S10。候选一：S10另一原批准事件/申请引用完整数据库事实门；候选二：正式bootstrap/root/permit登记与Source COMMIT，需独立152及尚未收口提交时钟门。选第一项，不以局部片段关闭原Task。

文件publication_store.py、formal_boundary.py、test_provider_capacity_formal_boundary_pg.py及本目录，沿原publication/formal Task scope和20:00租约。先新常量缺失RED，新增固定allocation SQL，复用原13字段event投影；按正向租户/maker/唯一approved checker.1/version1事件及原proposal approved/version2/三binding hash/当前期限/精确event模型hash、严格requestId/requestHash二字段payload校验。

在真实private read_capacity_approved_claims的原完整guard.check_proposal之后读取，不提前取得allocation锁或重排现有Provider/Evidence/withdrawal锁图；原Guard持有的proposal SHARE/Owner/Provider/neutral/withdrawal审计全部保留，新增查询不获取其他锁。原Source proposal runtime路径不变。返回仍APPROVED_CLAIMS_ONLY_NO_CAPACITY_NO_START，supplier_verified/execution_allowed false。

实际原批准夹具+SCRAM私有连接验证完整原claims正向，查询错maker/tenant/eventhash/requestID/requesthash/eventID/额外payload拒绝；原withdrawal两目标双方向实际COMMIT与原alias相邻，再formal/source-action/source PG累计。无DDL/真库/API/UI/Provider，完整SQLS01–S20/签发/消费者/自然首链仍未通过。
