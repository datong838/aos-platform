# 当前161恢复入口最小修复

Rules：AGENTS.md、231八步、栖月汇已批准全恢复方案。当前m1为8bf485fc7，authority AOS-001958；原parent Task/Lease唯一覆盖脚本及测试，未夺锁。

候选一：原卷升级后恢复入口版本/物理表数检查，已授权且无需真实库写；候选二：正式身份及当前四包安装恢复，依赖既有配置来源。先一。前一轮原生隔离维护围栏已交付，不重跑。

实际缺陷：require_identity先按EXPECTED固定159/647比对，再匹配代码头；即便真实库合法迁移161/650，也被误判身份漂移。保留数据库、cluster、组织名、双租户硬约束；增加显式物理schema合同159=647、160=650、161=650，只接受已登记且与当前代码头精确相等版本。未知版本、缺表、多表和跨租户均拒绝，不放宽准入或更改原数据。

修改scripts/a0v_qyh_restored_http.py及services/aos-api/tests/extension_runtime/test_qyh_restored_http.py。先以161/650真实迁移形状写RED，再最小修复；专项及相邻只读/正式OIDC/源码冻结门验证，并用独立已迁移161完整副本的原生只读metadata调用真实require_identity核验。无真实库迁移、服务重启或Host/Provider。不要把检查通过当完整恢复。
