# AIP-R00 执行基线证据包

结论：`GREEN`，允许进入 `AIP-R01 Provider 详情 canonical 化`。

本证据包只证明执行基线、恢复保障、租户边界与 R01 文件级方案已经冻结；不把历史提交、旧 Authority 投影或浏览器冒烟误写为 R01 完成。

## 已核验

- `w1-aip`、`m1`、`origin/w1-aip` 固定在同一 SHA `5b71a320cfa96b58093f6a3293264219d294c6ce`。
- tracked 工作树干净；既有未跟踪证据与运行目录均保留，未批量 stage、clean 或覆盖。
- 活动 Lease 为零；Alembic 唯一 head 为 `aip13_001`；R01 明确不新增迁移。
- 真实租户固定为 `org-org/dev-project`；`dev-org/dev-project` 仅作负向 canary。
- Watchdog LaunchAgent 每 30 秒巡检，当前正确返回 `turn-running`；31 个专项测试通过。
- Shared-memory validate 为 GREEN；Prime safe daemon 正在运行且启动参数不携带 Key。
- 内置浏览器确认旧 Provider 详情仍暴露明文凭据写入口，而 canonical runtime 已存在真实 Health/Capacity/Route readiness 权威；该矛盾由 R01 关闭。

## 继承警告

- 当前应用 OpenAPI 有 4297 个唯一 operation，冻结快照为 4264；此漂移早于 R01。R01 不新增路由，因此只携带警告，最终由 R33 全量封板统一关闭。
- Prime `list` 对旧 supervisor registry 所有权仍有残留警告；当前 socket/PID 可用。此项不阻断 R01，但必须在后续记忆维护波次复核。

权威机器可读结论见 `R00-ExecutionBaseline-Receipt.json`。
