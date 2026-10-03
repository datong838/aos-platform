# s3o-w-p｜原 BI Plan 受限事务接线计划

## 方案复习与边界

- 231-3：安装头先锁，批准/激活状态、ETag、签名来源与 Plan/Receipt 同事务一致；运行必须与安装启用分离。
- 原签名 Growth 1.13 全 schema 测试有获准但仅 test-only 的安装及六 Agent；仅用于克隆权限诊断，不外推为当前正式实例。当前真实库只读、Host/worker/Provider关闭。
- s3o-w-o 证明 SELECT-only 发行者可经受控 SECURITY DEFINER 函数锁精确安装头；原 `lock_for_transition_in_transaction` 两次 `FOR UPDATE`，`_load_record_by_pk` 默认 `FOR SHARE OF i`。原 `CurrentControlPermission` 还对 membership/marking 使用 `FOR SHARE`。任何这些行锁直接给发行者都会要求 UPDATE 权限。

## 文件级施工

1. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py`：在原签名全 schema 克隆里为非 owner BI 登录设安装 SELECT/RLS、仅该登录可调用的 test-only 安装锁函数；先 RED 证明原 prepare 仍在 `FOR UPDATE` 拒绝。逐次读出后续受限前置表的第一个真拒绝，不批量授予猜测性权限。
2. `services/aos-api/aos_api/asset_registry/installation_store.py` 与 `services/aos-api/aos_api/ecommerce_business_investigation_aip_authority.py`：仅在精确数据库角色 `aos_bi_plan_issuer` 路径调用精确锁函数，并无锁读取既有安装 Record；其他现有角色走原锁路径。函数不存在、身份不合、ETag/租户不合时失败关闭。此代码先以 test-only 函数在原方法克隆中验证，正式函数和最小 GRANT 的 migration 另波评审。
3. 针对当前首个后续权限拒绝继续梳理 `CurrentControlPermission`、resolver、Plan Store 的锁读/写表矩阵。若需要新增受控函数，先写设计和隔离 RED，不能为了通过直接授 UPDATE/runtime 成员/owner/BYPASSRLS。

## 验收与退出

- 专项覆盖原 BI prepare 的受限身份、错租户/ETag/签名、并发安装改版及同事务回滚；rebind/freeze 在正式来源具备后验证，缺项精确关闭。
- 原签名全 schema 独立测试、相邻旧路径、静态检查、无测试库/角色/OCI残留。只将实测通过的切片记 GREEN；未接完的前置表与正式 migration/凭据/当前库切换登记下波。
- 当前真实库切换必须先新一致备份、可恢复全链克隆和零执行窗口；本波不迁当前库、不造正式身份、不触发运行。
