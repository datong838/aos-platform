# W5c7t Fleet 控制面来源路由 verification

## 方案、实施与复审

计划 m1@`1cfa1318`；实施仅新增 `w5c7t-fleet-control-plane-source-routing-audit-20260925.md`，未改生产代码、DB schema、Runtime Host、worker、定义或源数据。审计按 W5c7b/g/s 将本地 launchd/Host lease、纯 Fleet 合同、独立真实 closure 门逐一划界：当前无正式全机控制面来源，不能实现真实 authority adapter；下一波盘点所有写路径 fence 覆盖。与方案一致，无把本机零进程/自报 true/签名形状当真实全机覆盖的风险漂移。

## 新鲜验证

- 首次专项因已停止的 `aos-dev-pg` 在 pytest fixture 建库阶段连接 5433 失败：93 errors、零测试进入逻辑。恢复既有测试容器后同命令重跑，Fleet 结构/签名/根/rollout 拒绝 + closure 门 **93 passed**；初次环境错误不计代码回归。
- A0-V 近期累计 no-effect 回归 **224 passed**、7 warnings、17.02 秒；未运行旧 12-source 长例，不把 W5c7n 的历史长例结果算作本次测试。
- 临时测试库 `aos_test_%` 计数 **0**，测试容器已停回原态；`git diff --check` 无问题。
- 浏览器临时 5174 只读验收：同步计划编辑器→整组采集，A0-V Canonical 版本 **4 已停用**；详情 **数据组已停用**，核对时间 2026/9/25 18:22:32 CST。页面有“待同步写操作（1）”，未冲刷、保存、启用、退役或执行；临时浏览器与 Vite 均已关闭。
- 真实 closure 只读组合门：`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false`、12 原 Run `running`、stalled Receipt 0，未决 `FULL_MACHINE_HOST_TOPOLOGY`、`FRESH_SINGLE_TRANSACTION_OWNER_GATE`、`SEPARATE_REAL_CLOSURE_PLAN_AND_UNIQUE_KEY`。严格时间资格晚于 2026-09-25 20:00:04.800482 UTC；时间达标也不自动授权。

## 退出结论与下一波

W5c7t 文档审计完成，但真实 A0-V 仍 `NO_AUTHORITY`：无旧 attempt 重发、无 `run_definition`、无商城源读取、无真实迁移/closure；230 L0 挂起，dev-org 零 canary，m1 不 push。下一波 **W5c7u** 先做所有可写 worker/Owner 启动路径的 lease/fence 传递矩阵与隔离验证计划；若发现未覆盖路径，先测试后最小修复，仍不触碰真实 Host/DB。
