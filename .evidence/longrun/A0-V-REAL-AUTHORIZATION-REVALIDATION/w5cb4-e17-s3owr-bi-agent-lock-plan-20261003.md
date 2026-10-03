# s3o-w-r｜六 Agent 当前版本行锁最小接线

## 上位方案与 RED

- 231-3 要求当前授权、身份、安装和状态变化在事务内复核并持锁；231-9 的六数字同事引用既有 AgentInstance，不创建第二身份权威。D-wave s3o-w-r 已登记此切片。
- 上波原签名 Growth1.13 全 schema 一次性库，在非 owner `aos_bi_plan_issuer` 下原 `SignedBIPlanPreparationService.prepare` 已越过安装与 membership/marking 锁，但六 Agent 的 `aip_agent_instance FOR SHARE` 触发 SQLSTATE42501，Plan/BI Receipt0。这是本波 RED，不是当前正式实例正向。

## 文件级实施

1. `services/aos-api/tests/extension_runtime/plan_restricted_issuer_case.py`：一次性库建 `PUBLIC` 撤权、仅精确 issuer 执行的同租户六 Agent `SECURITY DEFINER` 只读只锁函数。先覆盖 exact 六 ID、active/version、错租户/冒用/缺一/停用、并发变更等待与释放后的失败，保留测试对象清理。
2. `services/aos-api/aos_api/ecommerce_business_investigation_aip_authority.py`：只对真实 PG 且 `current_user=aos_bi_plan_issuer` 的原 prepare 使用该函数；其它角色继续原 `FOR SHARE`。仍由原版本数、六 ID 一致性检查判定，不自动创建 Agent/绑定。
3. 原签名全 schema 复测追下一处精确拒绝；若原 Plan/Receipt 可以同事务正向，再补重放/异体/失败回滚。相邻 BI、Agent、安装/权限测试单独跑，`py_compile`、diff、当前真实库只读与浏览器禁入回查。

## 受限克隆下一 RED 归类

六 Agent 行锁越过后，原 prepare 的新失败是测试专用 `s3owi_plan_receipt_guard` 拒绝 `bi_responsibility_plan.prepare`，错误 `PLAN_RECEIPT_UNPAIRED`；这不是正式表授权拒绝。只把该操作纳入同一 PlanRevision 配对校验，不削弱原 Plan/Receipt 同事务配对条件，再重跑原方法。

## 禁线与退出

- 不给 issuer `aip_agent_instance UPDATE`、runtime 成员、owner/BYPASSRLS；函数不能查询跨租户或未列 ID；需要原签名/安装/六实例每项均由原 Store 校验。当前卷不安装函数、不迁移、不补测试 Agent，Host/worker/Provider保持关闭。
- 若再遇其它原表 `FOR SHARE` 权限拒绝，本波只记录下一拒绝与 Plan/Receipt0，独立下波处理，不能批量放权或把一次性库当成正式首链。
