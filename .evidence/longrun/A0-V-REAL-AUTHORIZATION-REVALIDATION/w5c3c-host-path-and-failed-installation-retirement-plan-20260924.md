# W5c3c Host 路径修复与失败安装正式退休方案（2026-09-24）

## 方案依据

W5c3b `4075fd34`：唯一 prepare `b5175270-7de4-4608-b6aa-6a9713b66845` 正式 failed，三个 lease 均 released/observed，安装 approved/etag3、binding0、attempt0；Host 的 OCI driver 调 `docker` 时 `FileNotFoundError`，launchd PATH 缺 `/Users/ddt/.docker/bin`。`preparation_reset.validate_reset_snapshot` 只允许 applied 且有 succeeded apply proof，本安装不符合；`RuntimeUninstallGuard.before_uninstall` 的 approved 分支可在 binding0、unresolved0、unsafe resource0 时退休。九路 legacy/fenced、12 schedule off，不读商城源。

## 串行步骤与文件

1. 只读再确认失败 operation、三租约 released、安装 approved/etag3、无 binding/attempt、Host 已退出、九路/调度/canary；确认 Docker CLI 精确位置和当前 context 可读。任一漂移停止。
2. 最小修改 `deploy/dev/com.aos.a0v-w5c3-runtime-host.plist` 的 PATH，仅补入 `/Users/ddt/.docker/bin`；校验 plist、静态测试、`git diff --check`。在无运行中 operation 时，定向 bootout 已退出的唯一 label、bootstrap 一次，读回唯一新 PID/ACTIVE/空 liveTargets；不启动第二 Host。
3. 新增 `scripts/a0v_w5c3c_retire_failed_installation.py` 和定向测试，使用 W5c2b 已核安装身份与原 InstallationService.uninstall；全新 0600 intent/幂等键 `a0v-w5c3c-retire-failed-prepare-20260924-v1`，一次提交，不重用 W5c3b key。卸载前独立回读批准安装精确 lock、唯一 failed apply ID、三资源释放、Host 空载、无后续 operation、九路/调度/canary、安全预算；正式卸载后独立回读 uninstalled/etag4/activeRevision null、Command 唯一、历史失败及租约不可变、业务计数不变。
4. verification 落盘后提交 m1；下一波才使用原安装器创建 predecessor-free 干净 approved 安装，严禁在本波再次 prepare、verify、enable、切路由或调度。

## 停止条件

Host 仍运行、Docker 路径不可用、旧 operation/租约状态未知、卸载提交边界未知、原 Owner 拒绝、九路/调度/attempt/canary 漂移：冻结，不重发、不伪造状态；先只读核精确 Command/Receipt，再决定下一波。
