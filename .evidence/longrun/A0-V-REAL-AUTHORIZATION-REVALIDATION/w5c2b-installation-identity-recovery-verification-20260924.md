# W5c2b 原 installation 身份恢复与 DS 正式卸载验证（2026-09-24）

## 结论

**GREEN；只完成 DS 正式卸载，继任者仍未运行。** DS `c6812824-a0c3-4adc-9ebc-d56178ae135c` 经原 `InstallationService.uninstall`/`RuntimeUninstallGuard` 一次卸载，currentRevision6/etag6/state `uninstalled`，activeRevision null；Command 唯一且 `replayed=false`。新 successor `ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc` 保持 approved/etag3、无 binding/operation/resource。九路 9/9 legacy/fenced，12 schedules disabled，active attempts=0，canary=0。

## 身份与执行证据

- W5c2a 的旧键仍 Command0，不重用。主库原专用角色 `aos_a0v_installation_20260912` 为 LOGIN/NOSUPERUSER/NOBYPASSRLS/NOINHERIT、`aos_app` 成员、活跃连接0；旧私有身份文件缺失。按计划 `eca14554`，先在新私有 0600 intent 固定随机高熵密码，原角色密码只轮换一次；新 session 读回 `session_user=aos_a0v_installation_20260912`，受控采用 `current_user=aos_app`，密码未输出。新身份/result 文件均 0600，未创建新角色或授新表权限。
- W5c2b 新键 `a0v-w5c2b-ds-uninstall-20260924-v1` 的写前门禁再次确认 DS active/etag5、binding rev13/epoch7 disabled/fenced、三 lease released、全 operation 终态、W5b0 detach hash 精确、新继任者 approved、调度/attempt/canary0。仅一次原 Owner `uninstall` 返回正式 state uninstalled、uninstall evidence hash `sha256:9f25d2ccd9a9af9ca8ca52719e19774330c9bc9647053f5cdef1fceb98b4a51d`，非 replay。
- 独立审计 `W5C2A_DS_UNINSTALLED_GREEN`（复用原审计器但采用本波新 state/key）读回 DS `activeRevision=null`、唯一 Command、新继任者 approved/etag3、九路 9/9 legacy、12 schedules off、active attempt/canary0。8080 `/openapi.json` HTTP 200。
- 身份/卸载定向测试 4 passed，`git diff --check` 通过。旧离线客户端若仍持有旧密码将不能再登录；当前无活跃连接且旧文件缺失，风险保留。未读商城源、未启动 Host/PreparedJob、未启用调度或业务 Run。

## 下一波

W5c3 先方案，启动唯一独立 Runtime Host，精确读回 host/lock/PreparedJob 和当前 successor approved/etag3，再按原 lifecycle Owner 连续 prepare/verify；任何 Host 中断、lease 释放、operation 结果未知，先冻结并走正式 preparation-reset/direct successor，不能复活旧 DS 或在无 PreparedJob 时 enable。九路和 12 调度继续关闭。
