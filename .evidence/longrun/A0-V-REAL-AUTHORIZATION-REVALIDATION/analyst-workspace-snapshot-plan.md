# 经营参谋 canonical 只读快照端口

基线20619ca6。新增 services/aos-api/aos_api/extension_runtime/analyst_workspace_snapshot.py 及 tests/extension_runtime/test_analyst_workspace_snapshot.py。只读现有 canonical CaseHead/CaseRevision、Run、RunStateHead，不新建存储或复用旧 HTTP。宿主拥有数据访问，领域包拥有展示投影。

入口显式接收已建立事务的连接、服务端scope/subject及签名模块要求的markings。要求repeatable read或serializable，复用当前主体事务读取；固定SQL按scope筛选，最多50 Case与每Case10 Run，通过limit+1记录truncated，不伪造总量。Case与Run的state缺失/重复关联整体拒绝。cutoffAt为该事务读取时钟。响应只形成上一波快照合同，不调用模型或包、不提交事务、不执行命令。

“只读”指没有数据写入；因当前权限行FOR SHARE，本端口需要可持行锁的事务，不能配置为 PostgreSQL READ ONLY。生产连接权限和绑定/签名/route门禁仍需在正式调用链中接齐，本波不挂HTTP。测试验证scope参数、排序截断、缺失State、错误隔离级别、成员拒绝与无写语句；后续真实隔离PG验证同快照与分页边界。
