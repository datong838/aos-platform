# SC4-5l4 验证证据

基线 d9bb5ce3；m1串行；不push；230 L0挂起。

### SC4-5l4 固定完整快照事实查询验证

AnalysisSnapshotFactQuery仅接原SourceEvidence和精确ref；当前Owner重建全部原来源与计量后，以原固定Metric/AipAnalystQueryStore保存逐fact计数、unknown和字段/关系缺口。单完整组Evidence引用不截断来源；原requirement window/cutoff/expires、原actor、scope+Evidence+version幂等；固定partial/not_applicable，不认定经营质量。原raw request/result、hash、deadline、actor、列/行/来源全部精确重算回读。

Red模块缺失；首轮5 setup errors因测试TWA org主键误写org_id（实际id），修正fixture。第二轮3 passed/2 failed暴露原AIP8事件表SELECT/INSERT权限与FOR UPDATE冲突；补方案与单独Lease，把原Store尾事件更新锁改scope+query事务advisory锁，保留原CAS/RLS/append-only，不追加UPDATE权限。随后9 passed/31.26秒；最终新查询9+原Store回归3+两连接锁1+原SourceEvidence11共24 passed/62.41秒，7既有warnings。故障注入只在隔离schema以owner修改并恢复trigger；计数重新hash及confidence（原通用hash不含confidence）篡改仍被固定结果精确重算拒绝。Query写后source漂移全事务回滚。命名空间适配仅测试SQL表定位，原analysis/pending为named doubles；不是主环境12类892行验收。

AR2扫描1937/188/93，五类错误空；memory status强投影CURRENT，validate GREEN，authority AOS-000573。测试18432隔离schema；无主环境迁移/安装、无新增源读取/模型或外部业务写。保护overall-progress-20260913.md原+42行。主环境039–048升级、签名安装、真实新Run首链和八工作台仍未完成。

下一波SC4-5l5：新增显式SnapshotQueryQualityMeasurement并保留旧两个variant；当前精确查询+完整来源重验后生成正式逐类计量，Shop唯一scope人口策略不把不同类型相加，freshness使用原read_started_at；再接原QualityEvidenceStore，空分母/逐类阈值/撤权/过期仍拒绝。l6接原Outbox/Fulfillment预期状态转换，不能放入readonly pending callback。
