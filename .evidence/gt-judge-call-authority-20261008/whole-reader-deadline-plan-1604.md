# 完整新 Judge reader 原生截止时间验证

基线 AOS-001604 / 6c6c3b4679b0b7750e5503aa3df271be7e8913c0，五个父Task ACTIVE，唯一原线程，现有有效租约。沿原登记 reader-specific deadlinewait，不新建分支/写者，不动正式资源。

精确修改 services/aos-api/tests/aip/test_model_eval_judge_authority_pg.py；新增证据文件仅本Task文件夹。业务实现已有最后原审批/请求/Rule DB时钟复核，本轮先验证而非猜测修改。

方法：原完整 signed Rule/Suite/2个Model应用未过期时，新增独立 newJudge request/proposal/checker短时审批，原全局bucket前缀后同native SERIAL调用方创建Target与newJudge两parent，构造两case必要描述并调用原reader正向。随后DB pg_sleep等待审批截止，确认pg_stat_activity真实Timeout/PgSleep与独立数据库时钟已过期，再在同caller调用reader应拒绝；caller明确ROLLBACK，独立查询parent0、pg_xact_status aborted；既有committed Judge风险预留不删除。睡眠仅验证时间流逝，不能改称预算锁等待；fresh parents继承原锁，旧锁竞争测试保留。

完整原生节点用新attempt、当前HEAD/authority和精确现存容器/cluster/159库；终态后独立对账，不重发未知效果。专项通过后运行相关纯合同/Owner相邻测试，检查旧测试字节只追加、本次不涉及页面。仅阶段验证，不关闭五个parent或Goal，Source/actual allocation/Usage/finalizer仍待完成。
