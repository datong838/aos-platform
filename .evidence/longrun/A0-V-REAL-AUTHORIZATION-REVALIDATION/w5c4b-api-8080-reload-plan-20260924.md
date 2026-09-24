# W5c4b 8080 API 代码生效重启方案（2026-09-24）

用户已明确授权关闭并重启 8080。当前唯一 listener PID11654，cwd 为本仓库 `services/aos-api`，命令为 venv Python/uvicorn `aos_api.main:app --host 127.0.0.1 --port 8080`，启动于 2026-09-24 12:57 北京时间，早于本轮修复；`/v1/health` 200。截图所列十个提交短号（覆盖八族及补证）均为当前 m1 HEAD 祖先；本轮 `3acee1b9` 的 post-commit 审批续期修复也已通过 67/1 PG 测试。现运行进程不能视作已装载这些更新。

1. 重启前核唯一监听者/命令/cwd、8080 health、m1 干净、第三继任者 Resume 与 12 schedule off/零在途；记录 PID/启动时间。核现有 `scripts/demo/ensure-api.sh` 的精确 runtime guard 与启动参数。若监听者变化则不终止。
2. 使用仓库现有 `ensure-api.sh --restart` 正式重启单一 8080；不得启动第二 Runtime Host/Cron/快照 worker，不碰 18181，不读商城源。
3. 回读新唯一 PID、cwd/命令、新启动时间、health 200、OpenAPI 可读，正式数据库 cutover/业务计数/12 schedule/canary 不变。若重启失败，只按脚本日志定位与修复，不重复无边界 kill。
4. verification 落盘并提交；再回到 12 控制链构建波。重启只证明新代码装载，不把八族的在线门禁自动标绿。
