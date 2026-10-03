# s3o-w-q｜BI 独立发行者当前权限只锁接线

## 复习与判断

- 231-3 要求安装/操作当前权限在同一事务内复核，撤销/升级不能越过持锁窗口；前一波已为精确 `aos_bi_plan_issuer` 建隔离安装头只锁路径，原签名全 schema 的下一拒绝为 `meta_membership FOR SHARE`。
- PostgreSQL `FOR SHARE` 也要求 UPDATE 权限。不能给 BI issuer `meta_membership` 或 `authz_tuple` UPDATE、runtime 成员、owner/BYPASSRLS。旧 `CurrentControlPermission` 为其它角色继续用原 SQL。
- 当前测试的签名安装、六 Agent 仅是一次性库前提，不代表当前正式身份或业务首链。当前库只读，Host/worker/Provider关闭。

## 文件级步骤

1. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py`：在原签名 Growth1.13 全 schema 一次性库建两个只读、只锁、固定表名/search_path 的 SECURITY DEFINER 函数，分别返回同租户主体的原 membership 行、同租户 user_key/relation/object_key 的原 marking 行；只给精确 BI 登录 EXECUTE、撤销 PUBLIC。先 RED 确认原 prepare 仍在直接 `FOR SHARE` 失败。
2. `services/aos-api/aos_api/extension_runtime/current_permission.py`：仅对 `current_user=aos_bi_plan_issuer` 改由两个受控函数获取与持锁的同形状行；保留原业务 `require_control_role`、`require_target_markings`、租户 GUC、OpenFGA 禁入、安装 lock 解析与其它角色 SQL 不变。函数缺失/身份不合/错租户失败关闭。
3. 测试同事务 Plan/Receipt 正向、同键重放/异 body、错角色/marking/租户/主体、并发撤销等待及失败回滚；逐项追踪下一真权限拒绝，不批量授额外表权。旧权限及 BI/安装相邻回归分别运行。

## RED 后范围校正

- 当前权限两函数接通后，原服务确实越过 `meta_membership FOR SHARE`，下一处拒绝是六 Agent 的 `aip_agent_instance FOR SHARE`。本波把拒绝精确保留为 fail-closed 证据，Plan/Receipt 正向及重放延到下一处权限波，不为本波扩大受控函数表面。
- 相邻 `test_current_permission_pg.py` 的 6 个 `owner` 预期与现行 `control_policy.py` 的 `owner→admin` 映射冲突；这是旧断言漂移，按现行策略校正该测试预期，不变更产品权限实现。

## 退出与风险

- 只有原方法在受限非 owner 登录下配对 Plan/Receipt 且撤销并发稳定，才记本克隆切片 GREEN；测试函数不装入当前库。正式 migration/GRANT/身份文件/当前卷切换需要独立新全备、全链克隆、零执行窗口。
- SECURITY DEFINER 会越过 owner RLS，必须显式 tenant GUC、原列精确过滤、固定 `session_user` 与 `PUBLIC` 收权；返回最小原字段。函数可被受信 BI 登录用于读取其它主体，正式运行还依赖 OIDC 服务边界，不能将该数据库原语视为身份授予。
