# 当前161恢复入口代码验收

真实RED：schema161-red-r2.log记录160/161合法迁移形状均RESTORED_IDENTITY_DRIFT，2failed。第一次默认测试PG5433不可用产生2setup errors，不计RED；失败日志已移除默认示例连接字段，不重启旧端口、不重发数据库业务。

最小修复仅显式登记159/647、160/650、161/650物理合同；原数据库、cluster、栖月汇组织名、org-org/dev-project全部精确匹配，代码头仍须相等。未知版本、部分升级、多表和跨租户拒绝；原AUTH/OIDC/只读请求/WS/源冻结/Host禁入逻辑未改。

专项及相邻69passed、0skip、7既有warnings（4.86s），标准独立测试DB在18431原生建库迁移并清理，不使用真实卷。另原生独立完整副本只读核161/650，真实clone身份因数据库/cluster不同被拒绝；仅为检查schema分支的明确测试投影替换这两个字段后通过，不宣称原卷161或API启动成功。

方案与代码复核一致；物理合同将来新增revision须新审阅，不自动放宽。新增3表完整ACL/data验证依赖之前161真实演练，此处不重复或替代。真实源仍159、旧18080冻结API未切换；下一需原卷独占维护窗口和最新冻结源候选再由aos职责重启。无真实库写/旧Run重放/Host/worker/Provider或push。parent全恢复Task继续ACTIVE，本条只为代码子步证据，不出具整个恢复完成Delivery。
