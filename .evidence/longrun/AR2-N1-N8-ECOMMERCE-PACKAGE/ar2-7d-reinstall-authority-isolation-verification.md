# AR2-7D D6C 重装权威隔离验证

日期：2026-09-10
基线：`m1@3d430e0e`
结论：`AR2_7D_REINSTALL_AUTHORITY_ISOLATION_GREEN`

## Rules 与实现结论

- 以 closure manifest、231-3、231-6 D6/C10/J04/J06/J07/J11 和 D6C 细化施工卡为准；m1 单人串行，方案先于代码，最小修改，自测、证据后提交；不 push，230 L0 挂起。
- D6C 先执行同租户、同 package digest 的联合 PostgreSQL 反证。既有 installation、generation、execution epoch、Approval、DispatchRef、validate Receipt、group revision 与 RuntimeOperation 幂等作用域已经完整隔离，因此没有为制造代码量新增第二套重装状态、迁移或生产 guard。
- 重装通过全新 installation 与 generation 建立 runtime binding；在原九项 cutover group 已恢复 legacy 后，以当前 group revision 为 expected revision，使用绑定新 target 的新 Approval 完成 prepare、commit、validate、resume。最终 9/9 dispatch 原子指向新 installation/generation/epoch，group revision 严格高于旧代。
- 旧代完成 disable、9/9 detach、资源 observed release、runtime uninstall terminal Receipt 和 installation `uninstalled` revision 后仍保留审计历史；重装没有删除或复活旧代记录。

## 修改文件

- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`
  - 参数化既有 seed 与 cutover request helper，使同一租户可在原 group 上创建新 installation/generation 且默认测试输入保持不变。
  - 拆出“对既有 resumed runtime 执行 detach + release”的复用 helper，原调用路径保持原返回合同。
  - 新增旧代完整卸载终态到新代 validate/resume 的联合用例。

## 联合证明

- 两代 resource lease 的 `package_hash` 均为同一仓内 `sha256:aaaa...aaaa`，但 installation、generation、resource 与 RuntimeOperation identity 均不同。
- 新代 execution epoch 为独立初始值，不复用旧代 epoch；新代 9/9 dispatch 共享同一新 installation/generation/epoch/group revision，且 group revision 单调增加。
- 把旧 ActionApprovalEvent 注入新代 prepare，固定拒绝 `cutover approval is not bound to this exact group`。
- 把旧 CutoverValidateReceipt 注入新代 resume，固定拒绝 `validate Receipt reference drifted`。
- 保存旧 IssuedDispatchRef 后完成新代 resume；HostPort 在 serializable 锁事务内固定拒绝 `exact dispatch authority drifted`。
- 两代均使用 `runtime-apply / d6-owned-resource` 时得到两个不同 operation_id，证明幂等唯一性受 installation scope 隔离。
- 旧代 runtime uninstall Receipt、两条 disable/detach lifecycle Receipt 和 installation `uninstalled` revision 均可按原 tenant 回读。

## 验证证据

- D6C 单项最终：`1 passed, 63 deselected, 7 warnings in 3.48s`。
- 完整 ecommerce cutover PostgreSQL 最终：`64 passed, 7 warnings in 19.47s`。
- 宿主端口、canonical router、InstallationService/Store/API 邻接：`54 passed, 1 known boundary failure, 7 warnings in 5.87s`。
- 完整 `tests/extension_runtime`：`1250 passed, 28 skipped, 7 warnings in 87.76s`。
- Closure：`1710 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile、`git diff --check`：通过。

## 邻接限制与风险

- 邻接组合唯一失败仍是旧 `test_m5_ecommerce_composition_installation_pg.py`：fixture 中的 bundle 已带 runtime，却调用 legacy `InstallationRevalidator`；当前边界按设计在 submit 阶段拒绝 `runtime bundles require the isolated installation lifecycle`。堆栈未进入 D6C helper 或 uninstall 路径，没有放宽该边界制造假绿。
- 联合 cutover fixture 的 maintainer 只获 `SELECT`，HostPort 的 `FOR UPDATE` 需要其专用 host fixture 所授的 `UPDATE`；D6C 的旧 DispatchRef 字段反证使用临时 schema owner 的 serializable 事务，实际 HostPort 角色与 RLS 行为继续由 `test_ecommerce_growth_host_ports_pg.py` 覆盖。未在 D6C 中扩大数据库权限。
- D6C 是数据库权威联合证明，不冒充真实 OCI 生命周期验收。D6D 仍需在隔离 OCI 中固定同 digest 的 install → enable → 9 项派发 → disable/detach → physical release → uninstall → reinstall 新代全链证据。
- 未执行真实租户装卸、共享/生产迁移、Provider、费用、外部发布或 push。

## 内容摘要

- `test_ecommerce_growth_cutover_pg.py` SHA-256：`82c8eca80516b06c474842fdde180e0898c20fbbf7c6488810ddb0da2cb52fac`
