# 当前真实159完整恢复验收 r2

独立容量维护daabee6后，原exact实验卷/容器同CID/镜像/network-none恢复；旧失败aos_meta_head用户表0，原COPY事务明确回滚，未覆盖或重试旧DB。新qyh_current159_full_restore_r2_20261012独占意图/created/terminal0，原双copy SHA da795fb6... 相同，单事务pg_restore/原owner/ACL、replica仅该子进程，真实源未写。

647表全量行数与SHA全部相等。完整原pg_dump schema-only（含owner/ACL）仅去除随机restrict/unrestrict行后字节严格相等，SHA c33ac5e0306cc1e1eb86eb7c9ac65e9ccb0e6b89a34c0d34634f039b30d1cffa。12序列last_value/is_called相等；39非系统角色flags/rolconfig与12用户角色成员关系含grantor/admin/inherit/set逐项相等，未读或复制密码。真实源647指纹再次相等。

此前真实失败：tmpfs空间不足，实验bootstrap身份不同导致PG16GRANTED BY admin option拒绝，original bootstrap重建后shared Colima满。原失败/空DB/日志/角色诊断均保留，不将旧snapshot160演练作为本次最新备份恢复；本次成功由原source完整native restore证明。专项/相邻就是完整647+schema/owner/ACL+sequence+roles数据比对，不新添镜像实现的单测。脚本AST、具体diff与方案一致性复核通过；未改业务代码/页面，页面验收不适用。

仅本备份/全恢复Task可Delivery。连续零执行正式迁移窗、160迁移兼容、当前签名包/正式身份与Owner/安装配置/八工作台/自然经营首链仍待独立证据；原true source仍159且禁执行。所有private dump/schema/log保留0600，未提交数据，未删卷/备份、无Host/worker/Provider/商城源/旧Run/manual/unknown replay/push。长期Goal active。
