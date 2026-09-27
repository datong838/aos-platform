# W5CB4 安全全栈重启与浏览器验收计划（2026-09-27，操作前）

## 请求与事实边界

- 用户要求尽快完整启动 AOS 供检查。2026-09-27 现场只读：前端 8434 返回 HTML 200；8080/18181/5173 无监听；`colima-aos-extension` 的恢复 PG 18435 在运行，`aos_meta_head=a0v_092`，代码迁移头 `a0v_106`；容器 `/backup` 为空且声明的 Mac bind 源目录不存在。Runtime `unknown/fenced/epoch mismatch` 的既有证据未被启动前新权威推翻。
- 因此**禁止直接对当前恢复库升级或把它接入新版 API/自然 worker**。仅开前端或空开发库 API 不能称“完整 AOS”。本计划先恢复安全回退能力并在隔离克隆验证新版全栈；若克隆与真实 Runtime 均通过，再单列当前库迁移/切换执行门，不借用户“重启”要求跳过证据。

## 串行操作与停止条件

1. 只读冻结：核唯一监听/LaunchAgent/容器、`aos_meta_head` 版本、当前库尺寸、备份目标与空间；不得读商城源或旧 Run payload。若出现第二 Runtime Host、业务 API/worker 活跃或实例身份不唯一，停在只读对账。
2. 一致备份：在新私有目录保存 `a0v_092` 的 `pg_dump -Fc`，使用导出的 repeatable-read snapshot；文件权限 0600、目录 0700，记录字节数/SHA-256、版本与受限的结构指纹。备份输出不可放 Git，不输出凭据/业务内容；失败文件保留检查，不盲重跑。
3. 独立恢复：只在预先确认不存在的专用 clone DB 上 `pg_restore --exit-on-error`；独立连接核版本、结构与受限计数/指纹同备份前快照。若恢复或身份不一致，停止，不修改当前恢复库。
4. 克隆迁移：在 clone 上按现有 Alembic 单线 `093→106`，对 096 不可普通降级和 105 约束/锁风险逐步记录，设置有界 lock/statement timeout；任何失败只读核状态，不在当前库复试。
5. 启动门：只有 clone 到 `a0v_106`、全部启动 flags 显式关闭（Cron、AIP automation、snapshot、内容/反馈/Return/Review workers、SSH prebuild/Provider 等），且运行身份/目标 DSN、端口无冲突读回明确，才允许独立 API HTTP 验收。使用明确隔离标识，不能把 clone 页面称为当前真实经营实例；先 HTTP health/只读 scope，再浏览器核页面和离线/禁入提示。若 API 启动自身带隐式执行或需要 current Runtime ACTIVE，保持停止并记录原因。
6. 真正当前实例迁移/恢复是**下一独立波**：仍需当前一致备份可恢复、clone 全链演练、API/Host/worker 零执行窗口、签名安装及 Runtime 状态修复；在此之前用户只可检查隔离验收栈，不能宣称自然业务闭环。

## 文件级清单与验证

- 本计划及后续 `w5cb4-safe-fullstack-restart-verification-20260927.md` 记录逐步证据；必要的专用脚本仅能新增 `scripts/a0v_safe_fullstack_recovery_clone.py`，先复用既有 `a0v_installed_bootstrap_action_deploy.py` 的 snapshot dump/restore 约束，不改主库启动器、运行时代码或已有数据。
- 浏览器只验已证明安全的服务；操作后核监听、worker=0、第二 Host=0、租户零 canary 与不可变 Receipt 计数不增。停止条件优先于“尽快”要求。波次结束更新 D-waves/AOS 上下文、verification、m1 精确提交，然后回到 P2g30 主线。
