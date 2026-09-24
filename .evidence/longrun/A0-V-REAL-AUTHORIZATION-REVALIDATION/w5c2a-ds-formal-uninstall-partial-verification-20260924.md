# W5c2a DS 正式卸载部分验收（2026-09-24）

## 结果

**未卸载，未产生数据库效果。** 按计划 `a00aaa66`，W5c1 新继任者 approved/etag3、DS active/etag5/绑定 rev13/epoch7 disabled/fenced、原 detach Receipt、九路 legacy、12 调度 off、attempt/canary0 的只读预检 GREEN；新键 `a0v-w5c2a-ds-uninstall-20260924-v1` 私有 intent 已 0600 冻结。原 InstallationService 的一次调用在连接工厂打开前失败：旧 `a0v_ecommerce_current_reinstall._installation_connection` 固定读取 `/Users/ddt/work/projects/ai_agent/.aos-recovery-20260912/state/installation-control-identity.json`，该文件不存在。

独立只读核验：新键 `bundle_installation_command=0`，DS 仍 active/etag5/activeRevision5，新继任者仍 approved/etag3/activeRevision null；没有安装状态突变。未复用此 intent/key，不人工补造或复制登录凭据。脚本定向测试 4 passed（含 W5c1），`git diff --check` 通过。

## 下一波 W5c2b

先方案确认现行原 Owner 可用的受控 installation 身份/连接入口与授权，继续沿 `InstallationService.uninstall`、`RuntimeUninstallGuard`，不直接 DB UPDATE。若现行身份不可恢复，先修复执行器身份配置与受控运行环境；不得把旧已失效身份文件当必要真相。新波用全新目录与幂等键，在独立只读对账后再做一次正式卸载，未知边界仍不重发。
