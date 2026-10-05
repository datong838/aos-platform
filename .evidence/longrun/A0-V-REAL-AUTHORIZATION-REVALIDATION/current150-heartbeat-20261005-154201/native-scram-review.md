# 原生登录验证复审

本次真实隔离执行：first attempt错误口令经SCRAM拒绝、正确口令认证后被CONNECT门拒绝，finally已还原；r2仅额外临时CONNECT授权后完成原生session_user/current_user=issuer，org-org membership=1，dev-org canary=0。r2完整13目录snapshot与原a150 baseline精确一致，包括数据库ACL/角色；HBA原字节及模式恢复、口令文件删除。当前源及服务未变。

方案一致性限制：r2执行前核了NOLOGIN/password NULL和CONNECT false，未另采完整before快照；完整终后快照回读原a150 baseline精确一致。首失败原日志保留，r2使用独立phase；不存在未知结果重发。

代码只是绑定绝对路径/固定container的单次审计工具，不是通用维护执行器。跨文件/配置变更的finally无法保证机器断电恢复；intent存在时禁止复跑，须先只读对账。身份读取GREEN不代表Python入口、原审批事实读取、并发锁或三写正式COMMIT通过；完整restore Task不Delivery。

新鲜验证：实际SCRAM错误口令负门+原生只读事务+完整快照、git diff --check。无业务代码修改，不增加同构单元测试。仍待完整正式签发与当前库独立迁移/重启安全门。
