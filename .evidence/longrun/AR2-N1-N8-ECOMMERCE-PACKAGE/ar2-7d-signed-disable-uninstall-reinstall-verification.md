# AR2-7D D6D2 签名停用、卸载与重装联合验证

日期：2026-09-10
基线：`m1@b18d70e2`
结论：`AR2_7D_DISABLE_UNINSTALL_REINSTALL_GREEN`

## Rules 与范围

- 以 closure manifest、231-6 D6/J04/J06/J07/J11 和 D6 施工卡为准；m1 单人串行，方案先于测试实现，专项、邻接、全量、证据、提交后继续下一片。
- 只使用 `colima-aos-extension`、18432/18434 隔离 PostgreSQL、仓内生成的签名 bundle 与 localhost offline registry；不连接真实数据源，不调用 Provider，不产生费用，不执行真实租户装卸、共享/生产迁移、外部发布或 push。230 L0 继续挂起。
- D6D2 不修改生产代码，只增加默认不生效的测试 seam 和一个专用联合用例。

## 实现与方案一致性

- `signed_installation_case.run_signed_installation` 新增可选 `package_probe`。probe 只在显式传入时，于 offline registry 存活期间交出已发布 signed record、composition lock、真实服务和 revalidator；未传时原路径不变。
- `test_ecommerce_growth_cutover_pg._seed` 新增成对的 target installation/generation 参数。默认仍创建原有伪 binding；显式目标则只锁定并校验真实 ready+enabled binding 的 epoch/revision，不复制 installation 或 runtime authority。
- 专用用例在同一 tenant/schema 运行两代：签名 draft/submit/approve → runtime apply → verify → current configuration → enable → 9/9 activate；第一代再执行 disable fence/detach、真实 OCI stop/release 与装配 `RuntimeUninstallGuard` 的正式 uninstall；第二代从同一 composition lock、signed package 和 image digest 重建并再次完成 9/9 activate，最后 disable/detach/release。
- 测试 schema 补齐仓库已有 `w1e_001_bundle_installation_uninstall`，并仅为专用 NOLOGIN `aos_app` 连接授予 InstallationService 完成卸载所需的精确表权限；`ar2_018` 仍由数据库拒绝超级用户或非应用角色直接提交卸载权威，没有扩大 production role。

## 联合事实与反证

1. 两代 package hash、manifest digest、config digest 相同；installation id、generation、execution epoch、resource id、64 位 container id 均不同。
2. 每代 OCI 容器先由独立 `docker inspect` 验证 running 和 exact owner，再由既有 job cleanup 物理删除；随后 inspect 返回 absent，lease 为 `released/observed_release=true`。
3. 第一代 disable 通过 `EcommerceGrowthDisableDependent` 先围栏再将固定九项全部恢复 legacy；全部资源释放后，`InstallationService` 与 `RuntimeUninstallGuard` 在同一事务写 runtime uninstall Receipt、binding uninstalled/stopped 和 immutable installation revision/event。
4. 第二代 prepare 前，复用第一代 Approval 被拒绝；第二代 validate 后，第一代 validate Receipt 被拒绝；第二代 9/9 resume 后，第一代 DispatchRef 被 exact current authority 校验拒绝。
5. 第一代六条 installation revision、六条 event、五项 runtime operation、cutover Receipt、两条 lifecycle Receipt 和一条 uninstall Receipt 在第二代激活后仍可回读；同名 runtime-apply 幂等键使用 installation 后缀，不把跨 installation 请求误作 replay。
6. Configuration outbox 按既有 at-least-once 语义做最多 30 次有界 drain；旧代 terminal event 只 ACK，不重放已提交配置，目标 configure 必须观测为 succeeded 后才允许 enable。

## 验证结果

- D6D2 最终专项：`1 passed, 7 warnings in 5.80s`。
- 既有 signed worker configuration：`1 passed, 7 warnings in 11.28s`，证明默认 signed helper 路径不变。
- 完整 ecommerce cutover PostgreSQL：`65 passed, 7 warnings in 21.46s`。
- 完整 `tests/extension_runtime`：`1280 passed, 7 warnings in 158.04s`。
- Python compile、`git diff --check`：通过。
- Closure：`1710 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- 18432/18434 均无 `ar2_signed_*`、`ar2_cutover_*`、`ar1c_full_*` 临时 schema；`docker ps -aq --filter label=aos.extension.owner` 与测试 Registry/image 容器过滤均为空。
- 精确专项退出码为 0；其 pytest 进程退出后 JDBC cache 的 atexit logger 对已关闭 capture stream 输出一条 logging error，不改变测试结果、数据库提交或 OCI 清理，完整 extension runtime 回归未因此失败。

## 文件与摘要

- `services/aos-api/tests/extension_runtime/signed_installation_case.py`：`c4a789eeda5aff54803a66eea928884bc6d2c9ae78dd042c23ea6696b25bf04a`
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`：`8ce7f224d468bd4bbfb02a20ce5c5dbd4e78477badeab59c21dc43964c80099f`
- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_signed_lifecycle_pg.py`：`9df7ad882d8b673ff1744e03170732cb29ab24cb49d6ed60479981f0bbe207fd`

## 边界与下一步

- D6A–D6D 的退出条件全部满足，允许记录 `AR2_7D_DISABLE_UNINSTALL_REINSTALL_GREEN`。
- 本结论是隔离环境中的代码、PostgreSQL 与真实 OCI 联合证据，不是生产迁移、真实业务副作用、Provider、外部发布或 release authority。
- 下一步按 closure manifest 与 231-6 进入 AR2-7D 剩余可插拔累计验收；不得提前宣布 AR2-7 或 7E 完成。
