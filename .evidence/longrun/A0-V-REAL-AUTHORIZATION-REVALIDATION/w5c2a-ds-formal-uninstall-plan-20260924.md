# W5c2a DS 正式卸载而不启动继任者（2026-09-24）

## 现场与范围

W5c1 `ed5d9e73` 已新建继任 installation `ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc`，approved/etag3、无 runtime operation/binding/resource，composition lock 精确引用 DS active/etag5。DS 仍 disabled/fenced/released，九路 legacy/fenced、12 schedules off、attempt/canary0。独立 Host 尚未运行，当前没有 LivePreparedJob。

本波仅用原 `InstallationService.uninstall` + `RuntimeUninstallGuard` 正式卸载 DS。禁止直接 UPDATE、伪造 Owner、释放已 released 资源、重新 enable、启动调度/业务 Run。继任者继续 approved，不在本波 prepare。

## 固定步骤

1. 对 W5c1 独立 audit 再检查新 installation approved/etag3/精确 lock/currentInstallationRef 与零绑定；DS active/etag5、binding rev13/epoch7 disabled/fenced、三 lease released、全部 operation 终态，W5b0 原 detach Receipt hash 精确，九路 9/9 legacy/fenced、claim gate0、12 schedule disabled/attempt0/canary0；本波卸载键此前 Command 数0。
2. 冻结全新私有 0600 intent，按现有 `a0v_ecommerce_invalid_baseline_uninstall._build` 与原 installation identity，调用 `InstallationService.uninstall` 一次，if-match `"5"`，新键 `a0v-w5c2a-ds-uninstall-20260924-v1`。若异常或结果未知，不重发，先只读核 Command/installation/Receipt。
3. 独立回读 DS `uninstalled`、activeRevision null、继任者仍 approved/etag3、九路/调度/attempt/canary 未动，验证原卸载 Receipt 与未 replay；写 verification，m1 commit，不 push。

## 停止条件与下一波

新继任者/旧 DS 任一权威漂移、活跃/未知尝试、已存在卸载 intent/Command、原 Owner 拒绝或未知提交边界时停止写。W5c2a 完成后下一波 W5c2b 才启动唯一独立 Host 并连续 prepare/verify；Host 中断时走正式 preparation-reset/direct successor，绝不复活旧 DS。
