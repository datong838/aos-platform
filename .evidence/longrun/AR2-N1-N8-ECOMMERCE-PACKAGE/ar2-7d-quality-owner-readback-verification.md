# AR2-7D D1 质量 Evidence 精确回读验证

2026-09-09，基线91fd9559，m1串行；230 L0挂起，无push、真实源、Provider或外部发布。

- 原始JSON反例：将piiAllowed:false替换为0，旧读取器真实失败为DID NOT RAISE ValueError（1 failed，3.37秒；/tmp/ar2-quality-readback-red.log）。
- 修复后质量评估器与Evidence两个文件38 passed（9.16秒；/tmp/ar2-quality-readback-green.log）；包含真实PG写读、并发、外层回滚、canary、撤销，以及临时表伪撤销/隐藏真撤销双向反证。数据库仅自有18434一次性库，原18432保持停止。
- public表限定及原始payload摘要校验，不改变合法body或hash算法；本地独立只读审查无阻断项，不冒称外部Prime。实现SHA-256 d165500f2f8a203ff02975a52aeaec429a416ab664a37208c7cabab9af1e85f8。
- 闭包ar2-1扫描1701/分类87/迁移57，五类错误全部为空；git diff --check通过。
- 该证据仍factIds=[]，不认证来源，不产生业务事实或履约成功。方案与实现一致；完整Requirement策略、DataFulfill及D2-D4/7E待施工，AOS-000571不前推。
