# b81 独立Evaluator连接准入

模块缺失RED收集ImportError1error/7warnings0.40s保留；这是实现缺失，不是HTTP业务RED。新增生产模块只连接独立固定login，不创建role/grant，不接路由。复用Registry私有文件安全validator但不复用身份，loopback/exact DB/private path逐call复核、PG环境拒绝、固定超时/SERIALIZABLE/读写/GUC/session=current login、无危险attrs与任何角色成员。

真实独立随机LOGIN在一次性full-schema PG，应用常量仅测试patch为自有随机login；从未改变已有Registry/BI/runtime role。正向session/role/db/scope/isolation验证，业务INSERT42501；INHERIT/CREATEDB/CREATEROLE/BYPASSRLS/runtime membership、文件mode漂移/PGOPTIONS均拒绝且未yield。初9passed7warnings4.71s含原b45事务接缝2项。自复审malformed None/int先裸TypeError，实际RED2failed/7deselected/7warnings4.53s保留；最小catch统一安全Blocked，最终11passed7warnings4.60s。

新随机口令仅测试内存/私有临时文件，不输出、不复制用户凭证；role finally清理，roles-after=0。编译/diffcheck通过。仅新增两文件，不改现有Registry/BI/路由/migration/当前135/服务，无UI浏览器不适用；默认应用行为不变。

局限：连接身份不是表/列业务ACL完整准入，正式evaluator命令/HTTP未实现，source初始化/proof/head/八源尚未完成；本测试patch角色名是隔离算法证据，不是当前正式登录可用。scope GUC仅事务边界，真正调用者资源权限必须由正式命令检查，不能仅TenantScope参数授信。外部事务commit后的scope变化由命令生命周期管理，未声称连接任意复用可持续授权。

下一b82完善并实现独立schema ACL/正式proof与source head合同、真实PG ordinary/runtime绕过RED；先新角色无业务写权、只精确命令函数权限，source issuance独立权限，旧hash/Evidence兼容；实际HTTP/evaluator CAS/共同source锁逐项实现，不以连接可用或503占位收尾。authority1329/strong CURRENT，Goal active，真库迁移独立门不变。
