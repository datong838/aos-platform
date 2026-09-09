# AR2-7D D6D1 同 digest 物理 OCI 验证

日期：2026-09-10
基线：`m1@38744481`
结论：`AR2_7D_SAME_DIGEST_PHYSICAL_OCI_GREEN`

## Rules 与实现结论

- 以 closure manifest、231-6 D6/J04/J06/J07/J11 和 D6D 细化施工卡为准；只使用 `colima-aos-extension` 与 18434 隔离 PostgreSQL，m1 单人串行，最小测试改动，自测、证据后提交；不 push，230 L0 挂起。
- 引擎 `docker info` 实测为 Linux，SecurityOptions 同时包含 `name=userns` 与 `name=seccomp,profile=builtin`；真实 OCI 基础测试验证固定 digest/参数、owner/container-id 清理、userns、seccomp、取消与超时回收。
- D6D1 没有修改生产代码。测试 helper 只增加可选的 package hash、延后 record-created 和 concrete cleanup driver 注入；所有默认值保持既有 mock PostgreSQL 测试行为不变。

## 物理联合链

1. 在临时目录构建固定本地 image，记录其完整 `sha256` image/config identity。
2. 第一代完成 9/9 cutover resume；ResourceJournal 先持久化平台生成 name/owner，再由 `OciDriver.create_session` 返回真实 64 位 container id，随后写 `created` observation。
3. 独立 `docker inspect` 证明容器 running、用户为 `65534:65534`、network=`none`、rootfs read-only，SecurityOpt 同时包含 no-new-privileges 与指定 seccomp。
4. 第一代执行 disable fence、9/9 legacy detach，再由 `RuntimeUninstallCleanupExecutor(CleanupOnlyOciDriver)` 按 exact name/owner/container-id 物理删除；独立 inspect 确认 absent，lease 为 `released/observed_release=true`，之后才允许 runtime/installation uninstall 终态。
5. 第二代使用完全相同 image/package digest，但获得新 installation、generation、resource id 与 container id；完成 9/9 新代 resume 后再次 disable/detach、物理删除并确认 lease released。
6. `finally` 只按已记录 exact owner/container id 做兜底回收；用例结束后全引擎 owner label 查询为空。

## 修改文件

- `services/aos-api/tests/extension_runtime/test_ecommerce_growth_cutover_pg.py`
  - 为既有 resource helper 增加真实 OCI 两阶段 observation seam。
  - 为 detach/release helper 增加 concrete cleanup-only driver seam。
  - 新增显式 `AOS_EXTENSION_OCI_TEST=1` 的同 digest 两代物理 OCI 联合用例。

## 验证证据

- 引擎 SecurityOptions：`apparmor / seccomp builtin / userns / cgroupns`。
- 真实 OCI driver + registration/seccomp 基线：`21 passed, 7 warnings in 21.76s`。
- D6D1 单项：`1 passed, 64 deselected, 7 warnings in 4.95s`。
- 含 OCI 的完整 ecommerce cutover PostgreSQL：`65 passed, 7 warnings in 21.29s`。
- 测试前后 `docker ps -aq --filter label=aos.extension.owner`：空。
- Closure：`1710 scanned / 93 classified / 57 migrated`，五类错误数组均为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- Python compile、`git diff --check`：通过。

## 边界与下一步

- D6D1 证明 D6B journal、D6A detach、D6C 新代切换与真实 OCI 创建/删除能在同一权威链闭环，但固定 image 还不是完整 Registry 签名 installation 制品。
- D6D2 必须继续把仓内签名 Registry、verify/configure/enable、九项切换、卸载与第二代重装串成同一 tenant/schema；未完成前不宣布 `AR2_7D_DISABLE_UNINSTALL_REINSTALL_GREEN`。
- 未访问真实源、未调用 Provider、未产生费用、未执行真实租户装卸、共享/生产迁移、外部发布或 push。

## 内容摘要

- `test_ecommerce_growth_cutover_pg.py` SHA-256：`620acc29cc40557d618c4a78c348a51ae041efb49ba70ab3c9872a197b931152`
