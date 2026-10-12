# 当前Source发行兼容复验

复习原s3o-w-h/k/n与父Task source-writer-impact-review、issuer-baseline-review：完整生产接线/兼容证明是收紧Source ACL及配置消费的前置；禁止只撤权求目录通过。候选A当前Source issuer/protocol原生复验（已获隔离实施授权）；候选B安装独立审批（依赖合法管理员登录，已待答）。选A。

精确文件：本目录plan.md、run.py、original-native.log、before-source/private.json、result.json、verification.md。产品/测试源不改，仅调用原tests。原lab已停止，但实际同Task恢复容器qyh-source-writer-lab-20261011-recovered-20261012已运行并占18432；只读对账证明其label为父Task、image固定、无namedvolume、独立cluster7695402775127154735，原3issuer roles0、其他client0。复用该活跃容器，不启动旧lab、不夺端口、不新增写者。

真实源保持qyh-restored-pg-20261011/18446/原权威卷/161/650，Source仅READ ONLY全表指纹及原source ACL/Stage gate读回；不调用旧恢复/迁移脚本main。标准pytest session新UUID aos_test_*_ti4_test数据库并清理，源DSN18446绝不进入测试env；个别原native固定18432独立schema/DB/临时角色与权限按原fixture创建清理。AOS_SOURCE_ISSUER_PG_TEST与AOS_EXTENSION_PG_TEST显式开关，USE_SHARED_DATABASE保持未设置，关闭业务worker/Host/dotenv，原LOGIN仅测试身份，不当正式Owner/角色安装。

复验原test_aip_source_issuer_connection_pg.py及test_plan_receipt_writer_protocol_pg.py，记录每测试实际状态、xfail/skip不计PASS。区分标准session实际迁移头161与原protocol的最小schema；不会把协议测试当完整生产Source/八页面/首链。源650指纹与lab残留前后对账，当前库不写、不改成员/预算/资源，不重发unknown效果或原审批请求。异常保留诊断并读回同进程，不自动重启。

r1真实初始化错误：原session migration使用18432/postgres，160新表因此owner=postgres；161按原安全合同检查owner必须aos_app并拒绝，全部19case在setup报错，没有任何PASS/Source改动。保留r1完整log/JUnit，不修改161门或旧迁移来求绿。

r2连接安排：原硬编码issuer小schema/独立DB fixture仍用活跃18432 recovered lab；标准session新UUID全schema migration改用已登记capacity clone18431既有aos_app，符合原迁移owner语义。原clone旧Task缺当前Lease，renew明确拒绝且未改；当前同owner Source-boundary-rehearsal Task/Lease实际持有相同maintenance namespace，已只读对账并受支持CAS续期，旧Task/Lease不夺取/删除。capacity clone bb9c8b1a/cluster7695416748450308141无namedvolume/其他clients0。r2新目录/新intent，不重放r1任何未知外部效果；所有fixture UUID/临时role均新生成。两个环境均只测试身份，绝不是当前Owner/业务数据库。
