# W5CB4 当前最新代码／当前数据卷每日重启门（2026-09-27）

## 目标和现场

用户要求每天以当日最新 m1 代码与当前权威数据卷全面重启并自检，重启后继续研发，不等定时任务。当前 m1 `a615c552`，当前数据库 `aos_current_preview_20260927@a0v_106` 位于 `colima-aos-extension` 的 `aos-a0v-recovery-pg` 容器、命名卷 `aos-a0v-recovery-pg-data`；默认 Colima 已停止，不能误用。8080 旧 Python 进程、8434 旧 Vite 进程在；18181 无监听。最新代码含 a0v_107，但 D01 B/C1 未注册 Host，a0v_107 仅新增 append-only 结构；现有安全预览脚本显式要求当前库 a0v_106 且 migration disabled，已用当日代码读回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`。

## 本次和每日固定次序

1. 核 m1 HEAD/工作树、当前容器/卷/数据库身份、版本、安装/签名与端口；保留用户脏文件，不删库/卷/备份，不读商城源数据。记录代码 migration head 与库 revision 的差异。失配先 fail closed，不能靠换旧代码伪装最新。
2. 本次先按当前安全预览合同**重启现有 a0v_106 数据实例、API 8080、Vite 8434**，API 必须从当日 m1 源码启动、迁移 disabled、Cron/各 worker=false、Runtime Host=0；不打开 18181。数据库重启前确认目标仅 `aos-a0v-recovery-pg`，不操作其他容器。停止精确 PID 前再次核命令行和监听。
3. 服务回起后独立核数据库仍是同一卷/库/a0v_106、安装 approved、四包 published、binding 0；8080 受保护目录/健康 API、8434 页面、八工作台禁入摘要和至少一条核心只读功能做浏览器自检。故障优先修当前代码/环境，不以旧进程健康代替最新启动。
4. a0v_107 当前库迁移另立 D 波：先做不读取商城源内容的独立可信备份与恢复证明；当前主机侧旧 `/backup` 挂载路径不可直接见，不能假设它是备份。完成精确迁移与回读后再更新安全预览脚本版本门并重启。此门未过之前需明确报告“最新代码已重启于当前卷/a0v_106，D01 新表当前实例不可用”，不宣称当前实例完全升至代码 head。
5. 每日检查写机器时间、HEAD、卷、库 revision、端口/PID、页面与 Receipt、缺口；有代码变更则先方案→专项/累计→verification→提交。之后立即回 C2/BG-00 下一研发波，不以每日提醒代替主动 Loop。

停止：未知提交或数据库身份/安装/签名/卷漂移时先只读对账；不重发原 12 Run、不手工 `run_definition`、不打开 Host/Provider、不删历史。每日自动化只在任务空闲时接续，不能与同一 m1 开发并发写。
