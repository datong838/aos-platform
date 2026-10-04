# b59｜原安装卸载命令独立连接注入

## RED/实现/验证

- 上位231-3与 b58 两代次证据要求：普通安装 Store 不能为了卸载被整体切到 app 身份，运行 worker 仍不能终结；原 Installation 命令、terminal Receipt 和 CommandReceipt 必须同事务。先把 b58 signed fixture 的 `InstallationService` 普通 Store 改为 runtime Store，并注入单独 app Store，RED exit1 `TypeError: unexpected keyword argument 'uninstall_command_store'`。
- 最小生产改动仅 `asset_registry/installation_service.py`：构造器可选 `uninstall_command_store`，默认原 Store；`_execute` 只有 `UNINSTALL_INSTALLATION_OPERATION` 选择它，其他命令不变。handler 中原 Store 的 `*_in_transaction` 方法仍使用选中 Store 交付的同一个 `conn`；无跨连接终态写、无 HTTP 入参工厂、无数据库迁移/GRANT。
- 本地 signed 两代次隔离 PG/OCI 专项 exit0 `1 passed/7 warnings`；原 app/普通 Store 相邻三文件首轮 exit1，唯一旧 `test_runtime_control_plane_permission_locks_the_current_installation` 假连接无 `info`（b52 已记技术债）；排除该旧测试复跑 exit0 `21 passed/1 deselected/7 warnings`。`git diff --check` exit0。当前 preview 正式身份未齐，生产组合根尚未注入新 Store，仍失败关闭。

## 本波最新栈重启与真实状态复核（17:06 CST 起）

- m1 `81d48daf`，代码/当前库迁移均为 `a0v_135`；当前命名卷 `aos-a0v-recovery-pg-data` 挂载于 `aos-a0v-recovery-pg`，库 `aos_current_preview_20260927`。独立全备 `aos-recovery/.aos-current-backup-20261004-s3owaob25-XaGvdX/current-full.dump` 的 `shasum -a 256` exit0 为 `5614c2e76d4bc4abb3229461d44abb4ffa51749ddfc06f5b5f01ff29dfbbccbc`。本次没有重复宣称全恢复演练。
- 用服务项目虚拟环境运行 `scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json`，PG 重启前后均 exit0、`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，签名根、信任根、库身份、安装与版本一致。系统 Python3.9 对 `datetime.UTC` 的导入失败 exit1；改用 plist 指定的项目 Python 后通过，未修改数据或代码。
- `launchctl bootout gui/501` 依次停 Web、API，均 exit0；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，`pg_isready` exit0；再次签名预检 exit0；`launchctl bootstrap gui/501` 依次启 API、Web，均 exit0。新 API PID 22489、新 Web PID 22497，PG 18435/API 8080/Web 8434 监听，18181 未监听。
- API `/v1/ready` HTTP 200 `{"status":"ready"}`；经 Web 的 `/v1/health`、`/v1/ready`、`/aip/skill-publish` 与所测八个 `/workshop/*` 路由均 HTTP 200。HTTP 可达只证明最新栈启动，不证明业务链。
- 当前库 `BEGIN ISOLATION LEVEL REPEATABLE READ READ ONLY` 查询 exit0：`aos_current_preview_20260927@a0v_135`；正向租户 Installation `current_revision=3/active_revision=NULL/etag_version=3`，`aip_capability_binding=0`、`extension_runtime_binding=0`、`extension_runtime_host_assignment=0`；事务 `ROLLBACK`，无写入。
- Codex 浏览器当前发布页：电商工作台仍“暂无可见工作台入口”，37 条仅已评测/已发布0，正式发布决定、Logic 精确版本、模型路由策略三缺口；“发布此修订” disabled。浏览器读取证据保存在本轮工具输出，未导出独立截图。Runtime Host/worker/Provider 均未开启。

结论：`81d48daf` 的受限运行卸载命令连接选择逻辑已随最新 API 加载，b59 代码验证通过；当前安装仍失败关闭，不能把本地两代次签名测试、HTTP 200 或页面渲染算作当前真实实例首链。

## 下一步

- b60 独立正式私有凭证与专用低权连接预检，并在生产组合根仅为运行卸载注入；当前库角色/ACL 迁移与 Capability/安装锁/可信 evaluator 共同排唯一136，需新备份、全恢复、零执行窗口。当前实例/首链仍未通过。
