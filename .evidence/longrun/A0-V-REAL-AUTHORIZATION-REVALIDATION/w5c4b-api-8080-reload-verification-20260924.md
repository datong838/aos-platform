# W5c4b 8080 API 生效与启动权威验证（2026-09-24）

## 结果

8080 现由唯一 **launchd** 作业 `com.aos.a0v-api-8080`/PID31967 管理，进程 2026-09-24 15:41:48 北京时间启动，晚于截图八族提交及本轮核心修复；命令使用本仓库 `services/aos-api/.venv/bin/python -m uvicorn aos_api.main:app --host 127.0.0.1 --port 8080`，cwd 精确为 `services/aos-api`。`/v1/health` 与 `/openapi.json` 均 200；运行权威 guard `RUNTIME_OWNER_EXACT`，PID 文件已与唯一监听者同步。第三继任者 W5c3x 正式审计仍 `RESUME_GREEN`，九路 extension、Runtime rev6、12 schedule off、业务计数未变。

## 失败与修复边界

首次按旧 `ensure-api.sh --restart` 重启时，脚本用 micromamba Python3.12，因缺 `pglast` 导入失败；这是新进程启动前失败，不涉及业务提交。补丁显式选仓库 API venv，`bash -n` 通过。随后旧脚本因 PID 文件缺失，误把 launchd 自动拉起的健康进程判为无主，进入 stop/fallback；自身 PID31972 因旧环境清单根目录不存在退出，launchd 的 PID31967 再次持有端口。发现精确 `launchctl` 作业后停止重启，没有再次杀健康进程。

脚本现优先识别 `com.aos.a0v-api-8080`：普通 ensure 验作业 PID=唯一 listener、命令/cwd/health 并同步 PID 文件；显式重启才走 `launchctl kickstart -k`，不再与守护进程竞争。无 launchd 作业才使用原兜底流程且明确 venv。脚本测试 **19 passed**，实际普通 ensure 返回 `RUNTIME_OWNER_EXACT`/OK。未安装依赖、未新起 Runtime Host/Cron/快照 worker、未读商城源或手工 Run。

本波证明当前 8080 已装载更新后代码并稳定服务；截图八族的各在线门禁仍须逐项复核，不因“重启成功”自动标绿。下一波回到 12 条新控制链的当前授权预检。
