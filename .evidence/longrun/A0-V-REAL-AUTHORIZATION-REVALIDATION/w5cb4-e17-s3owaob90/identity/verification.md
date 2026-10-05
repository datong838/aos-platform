# b90 身份切面验证（完整 evaluator 尚未完成）

基线33c827b3；Authority1329。原始RED red.log：3failed/1passed/7warnings/4.78s，实际PG反向成员及搜索路径未拒、硬链接未拒；原正向成员已拒。最小修复：双向成员、固定pg_catalog/public/pg_temp与回读、private单link、require_auth SCRAM及实际used_password。没有开生产LOGIN/业务ACL。

green-r1.log 4passed/4.69s；green-actual-scram.log 5passed/4.58s。最终green-temp-shadow-final.log **44passed/2xfailed/7warnings/5.07s**，五模块包含原evaluator malformed config两例、Binding readiness、Model resolver及Capacity authority。实际专用测试LOGIN认证、错误密码拒绝、反向成员commit后新连接拒绝、临时同名ModelRoute表仍解析public原表。Session authorization反例仅证明身份检查，不能代替SCRAM；本轮没有正式JWT/完整八facts正向。

两个严格xfail仍保留：正式来源许可未接旧readiness、激活最后事务缺签名安装复核。未运行旧evaluator整个模块，其random-role fixture使用DROP OWNED；本轮仅运行该模块无此fixture的malformed config测试，实际正向连接在新增测试完成。不得把44称为完整evaluator/全API累计验收。

所有测试句柄1434/47271/89342/28759/1070均terminal；PG串行。cleanup.json实际回读49旧测试库不变；测试evaluator最终0，三个迁移产生的临时NOLOGIN Source角色安全属性false/成员0/共享依赖0后精确DROP，无DROP OWNED。两文件编译通过，精确diff检查通过；无页面变动，浏览器不适用。当前135库未迁移/重启，用户九M未改，Host/worker/Provider/商城源/旧Run/外部效果关闭，无新增模型调用。

复审：实际私密文件在每次连接前重验；不借Source/Registry权限；原单commit/异常rollback结构保持；固定pg_temp末位防共享读取器表名解析被临时表污染。本切面改变正式连接要求，非SCRAM或不安全配置将拒绝，正是既定专用身份合同。完整evaluator本轮仍无代码入口、a143权限/proof写入未实现；plan.md审查继续，特别是Health新观测并发、完整Source批准消费者复用和逐表锁列/RLS。
