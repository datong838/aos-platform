# 经营参谋同事务快照验证

基线20619ca6。宿主固定scope查询原canonical Case/Run/State，当前主体事务复核、repeatable read/serializable、limit+1及truncated，缺少state或重复run拒绝，未写业务数据、未自行提交。包内领域投影继续负责source hash和跨记录校验。

16项单元/包内/真实隔离PG测试通过，7项既有依赖警告。PG同事务第一次读取1 Case/1 Run，另一连接新增Case后仍为1，下个事务为2；外租户Case被固定scope排除。该测试使用隔离最小表验证SQL与快照，不替代正式数据库角色/RLS交付验证。ar2-7 1838/分类163/迁移93，五类错误为空；diff --check通过。

未挂HTTP或真实包IPC。接线复核发现API与当前运行宿主分进程，而LivePreparedJobDirectory为进程内目录；不能在API直接构造CurrentInstalledPackageInvoker后假定能访问宿主持有的实例，也不能另起第二实例。下一波先补跨进程只读请求到既有单写者宿主的正式调用方案及清单，再接包内投影，不绕过当前安装/签名/主体权限。真实首链和八场景仍未完成。
