# AR2-7D D6B2B runtime uninstall wiring 验证

日期：2026-09-10
基线：`m1@4c96b1f7`
结论：`AR2_7D_RUNTIME_UNINSTALL_WIRING_GREEN`

## Rules 与实现结论

- 以 closure manifest、231-6 D6/C10/J04、D6 施工卡和 D6B2A 已封存 authority 为准；m1 单人串行、最小修改、自测、证据后提交；不 push，230 L0 挂起。
- `InstallationService` 保留可选 guard 以兼容既有隔离构造；生产 canonical HTTP builder 与 runtime control plane builder 均注入 exact `RuntimeUninstallGuard`。
- uninstall 固定顺序为 replacement leaf guard → runtime uninstall guard → installation evidence/append。runtime authority 不全或 guard 异常时，不读控制时钟、不写 installation revision；既有 idempotent command 事务负责整体回滚。
- rollback、普通内容包、read-only projection 和其他安装状态转换不调用 runtime uninstall guard，保持既有合同。

## 修改文件

- `services/aos-api/aos_api/asset_registry/installation_service.py`：在唯一 uninstall transition 中调用可选 runtime guard。
- `services/aos-api/aos_api/asset_registry/control_wiring.py`：canonical HTTP 与 runtime control plane 两处注入 concrete guard。
- `services/aos-api/tests/extension_runtime/test_lifecycle_service.py`：验证调用顺序与失败零 append。
- `services/aos-api/tests/asset_registry/test_control_wiring.py`：验证两处生产装配均不可缺 guard。

## 验证证据

- 服务、生产装配、安装存储与 HTTP 契约：`30 passed, 7 warnings in 11.41s`。
- 完整 ecommerce cutover PostgreSQL：`63 passed, 7 warnings in 18.84s`。
- 签名安装基线：`33 passed, 9 skipped, 7 warnings in 17.64s`。
- 完整 `tests/extension_runtime`：`1249 passed, 28 skipped, 7 warnings in 87.79s`。
- Closure：`1710 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile 与 `git diff --check`：通过。

## 邻接限制与风险

- 额外运行旧 Workshop projection/uninstall migration 组合时，13 项通过、8 项在 submit 阶段失败；失败原因为旧 fixture 的 bundle 已带 runtime，而 legacy `InstallationRevalidator` 按已封存边界拒绝“runtime bundles require the isolated installation lifecycle”。堆栈未进入本次 uninstall guard，未修改该边界或测试制品来制造假绿。
- D6B 已完成资源一次性清理、数据库终态 authority 与生产 wiring；D6C 的重装新 installation/generation 隔离及 D6D 的同 digest 隔离 OCI 联合验收仍未完成。
- 未执行真实 OCI 删除、真实租户卸载、共享/生产迁移、Provider、费用、发布或 push。

## 内容摘要

- `installation_service.py` SHA-256：`3eb7097abe557cc82832d159fa112f4f141c8e6766dba88afe5607bb1e810797`
- `control_wiring.py` SHA-256：`e2c1637eccf8d06932be242af4571c356eafe1bf592ed3e2860bf9693510f6b2`
- `test_lifecycle_service.py` SHA-256：`a600a51e789b06c35fb61e086baa8d4f22ea9a314da1bc318717aeb5e4686725`
- `test_control_wiring.py` SHA-256：`8b4d4977474cd01a2f8d47effe639ff425cea5089fd754d29b682a9c4859c4b4`
