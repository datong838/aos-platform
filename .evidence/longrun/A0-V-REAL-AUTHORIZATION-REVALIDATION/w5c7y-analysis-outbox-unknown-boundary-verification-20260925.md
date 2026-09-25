# W5c7y Analysis Outbox unknown 边界验证（no-effect）

## 结论

本波完成只读审计，不修改生产代码、不触碰真实 A0-V attempt。Outbox 的 Python `unknown` 返回值不等于持久化 `unknown`：若 `mark_unknown` 自身失败或提交结果不明，旧 `claimed` 在 lease 过期后仍可能由 `claim_next` 再领取（新 attempt）。因此当前不能宣称未知结果后的自动重领安全，也不能据此启用真实 Runtime Host lease。

序列与三类不明结果详见同目录 `w5c7y-analysis-outbox-unknown-boundary-audit-20260925.md`。delivery lease/token 不是 Host epoch。下一波 W5c7z 在隔离 PG 复现 `mark_unknown` 失败/ACK 结果不明的再领取资格，再定最小修复；真实旧 generation 绝不重发。

## 本波九步与证据

1. 对照 231 上位方案、A0-V no-effect、W5c7v/x、m1 与项目 authority；本波开工未获得真实效果权限。
2. 方案先提交：`ad00a483`；仅审计 worker、Outbox、coordinator、SQL 和已有测试。
3. 审计文件落盘：拆分 claim、coordinator 多提交、complete/mark_unknown/reconcile 的边界。
4. 专项：worker/Outbox/Coordinator 组合 `19 passed, 3 errors`（39.65 秒）。3 个 Coordinator PG 参数例在 fixture 的 `ValueError: analysis snapshot group differs from original source` 处报错；单独重跑首例仍同错（约 11 秒）。不写成专项 GREEN；它们未走到本波所需的 unknown 负例。
5. 近期 A0-V 短累计 `239 passed, 7 warnings`（18.02 秒）；历史长例不重算。
6. 内置浏览器只读：2026-09-25 18:59:40（Asia/Shanghai）回读 A0-V 配置 rev4 已停用、运行状态“数据组已停用”；页面仍提示“有待同步写操作（1）”，未冲刷。
7. 双向复审：没有新代码；实际 SQL 允许过期 `claimed` 再领，worker 的 `mark_unknown` 异常分支仅记录日志，与审计结论一致。Coordinator PG fixture 失败作为未闭合测试风险保留。
8. 本文件与审计提交后更新 AOS/Prime 投影，校验 CAS；不把审计视为实运行业务 Receipt。
9. 自动进入 W5c7z，先方案、隔离 PG 负例，再讨论修复。

真实门禁同波只读回读：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、`runningOriginalRuns=12`、`stalledClosureReceipts=0`；缺完整机器 Host 拓扑、Fresh 单事务 Owner 与独立真实关闭计划/唯一 key。24 小时严格阈值是 2026-09-25 20:00:04.800482 UTC，时间到达本身不授权。Store Receipt26、ecom_link0、projection pending0 等沿用前波最近证据，本波未把其当作新写入许可。

边界：m1 单写不 push；230 L0 挂起；商城源行不读；`dev-org/dev-project` 仅隔离 canary；未知结果不重发、不手工 `run_definition`。
