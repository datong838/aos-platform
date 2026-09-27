# W5CB4 E13：当前安装 Apply 尝试被正式拒绝，边界冻结（2026-09-28）

## 结果与停止决定

本波**未激活安装**。按计划只在 `/apollo/assets` 产品入口对唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 提交一次通用 `Apply`；2026-09-27T23:06:25.418778Z API 对 `POST /v1/bundle-installations/ccdcb0f0-1040-4bc6-aa0c-d045f5689813/apply` 返回 HTTP 409（trace `1b29f534-4fb8-46d0-9e3a-f2cec2830611`）。页面回报资源状态变化。随后只读对账确认当前状态仍为 `approved`、revision/ETag 均 3、`active_revision=NULL`、安装事件仍 3 条，`extension_runtime_operation=0`、`extension_runtime_binding=0`。没有执行 Verify，也没有第二次 Apply 或换键重试。旧命令边界在本波冻结。

这是**服务端明确拒绝且独立回读未见提交**，不是把 409 猜作成功；也不把页面错误文案当作真实状态漂移。产品页的通用操作入口与运行包的正式生命周期不一致，下一波须修正入口并使用隔离 runtime 路径，不能绕过后端围栏。

## 步骤与证据

1. 复习 231/231-9 BG-00、E12 与本波计划 `7793b46b`，确认只处理当前安装指针，不启业务来源、Host 或 worker。
2. 原命名卷 `aos-a0v-recovery-pg-data` / 库 `aos_current_preview_20260927` / schema `a0v_109` 执行只增备份：`/Users/ddt/work/projects/ai_agent/.aos-e13-current-backup-X7AHiU/aos_current_preview_20260927_a0v109_before_apply.dump`，3,893,668 bytes、权限 0600、SHA256 `3cb3ca4d3f5280c3d82c552a39e6adbf5b92acc42af3087434a1a66437e57e17`。备份未覆盖旧卷或旧备份。
3. 浏览器一次 Apply 得到上述 HTTP 409；不发 Verify。
4. 当前卷只读复查：`bundle_installation` 连接当前 `bundle_installation_revision` 得 `approved|3|3|NULL`；该安装事件 3 条、runtime operation 0、binding 0。代码 `asset_registry/installation_service.py` 的通用 Apply 调用 `InstallationRevalidator`；`asset_registry/installation_revalidation.py` 明确对 `manifest.spec.runtime is not None` 抛 `RegistrySnapshotStaleError("runtime bundles require the isolated installation lifecycle")`。`tests/extension_runtime/signed_installation_case.py` 断言运行包通用 Verify 必须拒绝，表明这是有意的安全界限。此路径应使用 `bundle-runtime-installations` 的 `runtime-apply` → `runtime-verify` 及运行 Owner、健康和资源证明，不能直接改安装指针。
5. 停止门已触发，Verify **跳过**。不删除数据、不读取商城源、不手工 `run_definition`、不重发旧 12 Run。
6. 专项回归：`test_installation_revalidation.py` + `test_runtime_release_artifacts.py` 17/17；当前 API `/v1/health` 为 `ok`、`/v1/ready` 为 `ready`、Web 8434 为 HTTP 200，18181 无监听。此为运行可用性，不是业务首链通过。
7. 方案/代码复审发现本波计划把通用 Apply 误当作运行包激活路径；服务端正确 fail closed，页面入口仍误导。无代码修改，因此本波不需为拒绝修改生产状态。
8. 本文件落盘，明确失败及后继路径。
9. 精确提交本文件；下一波 E14 先复习正式 runtime 安装产品/技术方案与当前独立凭据/Host 现状，细化文件级计划，再以最小改动校正 UI 操作分流和可执行的正式 runtime 准入；如当前身份/资源门不成立，只做安全的产品诊断和实测准备，不拿人工或旧库捷径冒充激活。

## 仍未完成

安装 `active_revision` 为空；源/管道/Selection、Runtime 绑定均未建立，真实首链未自然运行。E13 的目标没有达成，不能标绿；E14 是直接后继而非本波悄悄重试。
