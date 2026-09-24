# W5c3c Host 路径修复与失败安装正式退休验证（2026-09-24）

## 结论

**GREEN，限 Host 空载与失败安装退休。** launchd PATH 增补 `/Users/ddt/.docker/bin` 后，唯一 Host 重新加载为 PID 15014 / `RUNTIME_HOST_ACTIVE` / `liveTargets=[]`；未重用旧 prepare key，未启动新 prepare。W5c3b 失败 installation `ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc` 经原 InstallationService 正式卸载至 uninstalled/etag4，不能再参与运行。

## 证据

- 方案 `09b84930`。`plutil -lint` OK；精确 PATH 下 Docker context `colima-aos-extension` server 29.5.2 可读；仅对已退出的 `com.aos.a0v-w5c3-runtime-host` 定向 bootout/bootstrap 一次。最初启动瞬间旧状态文件尚未更新，未据此写业务；随后新 PID 15014 状态回读通过。
- 卸载预检精确锁 `sha256:90de41222929fb40a52a33f7222b818a4d3a94c92a6b07251e8a6825d41783e4`、唯一 operation `b5175270-7de4-4608-b6aa-6a9713b66845` 正式 failed/revision7、三资源 released/observed、binding0、attempt0、九路 9/9 legacy/fenced、12 schedule disabled、canary0、Host 空载。原安装身份复核通过。
- 新幂等键 `a0v-w5c3c-retire-failed-prepare-20260924-v1`，0600 intent/result，原 Owner 卸载仅提交一次且 `replayed=false`。正式 Receipt 为 uninstalled/currentRevision4/etag4/activeRevision null；独立 audit 再核历史失败 operation/三资源不变、Command 唯一、Host 同 PID 空载、受控源 claim=40、meta_schedule_run=53 未变。
- `test_a0v_w5c3c_retire_failed_installation.py` 6 passed，覆盖非正式失败和未释放资源的拒绝；`git diff --check` 通过。未读商城源、未启用九路/调度、未触发业务 Run。

## 下一波 W5c3d

先方案并复核 predecessor-free 安装路径与当前无 active baseline 的权威；使用原签名包和全新幂等键创建干净 approved installation，保留九路/调度关闭、Host 空载。其后独立波才以唯一自然 Host 再做 prepare/verify。不得引用已卸载 DS 或本次失败安装作为 active predecessor。
