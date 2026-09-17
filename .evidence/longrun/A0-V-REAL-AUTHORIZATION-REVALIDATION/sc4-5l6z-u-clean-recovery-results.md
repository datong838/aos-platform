# SC4-5L6Z U clean recovery 与 crash-rehydrate 验证

日期：2026-09-17
基线：`0d72f245`，分支 `m1`，单写者，不 push，230 L0 保持挂起。

## Rules 与范围

按 `sc4-5l6z-t-clean-successor-recovery-plan.md` 修订执行。方案先行、每次写前 exact 回读、
未知结果不重发、正租户 `org-org/dev-project`、负租户只作零安装 canary。没有修改商城源库、
运行宿主内核、安装当前性守卫或业务表；S/T/U 的写入全部经已有 Lifecycle、Installation、
Configuration Service 和唯一 Runtime Host 完成。

## T 真实 Red 与安全收口

T `b6f774c6-d544-45ab-bcfa-7cd8b824c1ed` 错把已 detach 的 S 作为 replacement predecessor。
apply operation `0819bf9d-45bf-47ac-a60d-c438ff1ecd4e` 于 01:02:20Z 成功；verify
`bb953ef8-f925-492c-bfcc-82a2e684159e` 被 Host 领取后命中 `CurrentInstallationStaleError`，
三资源在 01:02:41Z 起释放。该拒绝证明 predecessor active-baseline 守卫生效，未修改内核绕过。

verify deadline 到期后，正式 `reset_preparation` 把 T 从 `applied@4` 回到 `approved@5`，原 verify
被固定为 `failed / PREPARATION_OWNER_LOST`；随后 T 通过正式 uninstall 到 `uninstalled@6`，无 binding、
三资源 released/observed、零未决 operation。原 T 脚本已封存为只读历史失败证据。

## clean U 生命周期

U 创建时不传 `currentInstallationRef`：

- installation：`277fe01c-ece7-4c8f-9500-fc1ba0d5f050`
- lock：`sha256:15ac55d0ca7098c4df286ad70b6a20e79c327b0ec9c53baceea7cbb7059fcae8`
- 包版本：core 1.4.0、niushop 1.23.0、growth 1.10.0、operations-base 1.2.0
- generation：`f576ea28-7c2b-4032-8b4c-9d196df6228e`
- config：`7b0bfd0f-c1ca-474b-be32-de0cf47e5308@1`，hash
  `sha256:06f6e7e82a6f96dca862505df9558abcefd16329eb26c7994fd8d18e6d1d2130`

唯一 Host 自然消费 apply `f8bebde6-3f9f-4672-89d7-a93e4fd56c56`、verify
`4dbea41d-2b42-4340-926e-857ae57160c5`、configure
`6d937fe2-b713-4829-a0bf-5f7495dc9c57`、enable
`1c5ea17f-cc4c-404e-be68-59af02ef8e0e`；四项均 `succeeded/succeeded`。终态为
`active@5 / binding revision4 / epoch3 / enabled / ready / unfenced`，三资源
pending/unreleased，canary installation 0。

九项经营路由仍为 `legacy / fenced / groupRevision62`，未在安装恢复阶段提前切流；全租户
runtime operation 未决数为 0。

## crash-rehydrate

旧 Host PID 48502 在 U 活跃后先产生三次 lease renewal，其中验收前两次为 01:13:02Z、01:14:05Z。
随后以 SIGKILL 模拟进程 crash；数据库和容器保持运行，U 三资源未释放。新 Host PID 49049 于
01:15:33Z 写入 `runtime_lease_rehydrated`，binding revision4/generation 与 U 精确一致；随后在
01:15:34Z、01:16:35Z 两次 `runtime_lease_renewed`。状态文件持续只有 U 一个 live target。

## 验证

- S 退役、T 历史失败、T→U 恢复、RuntimeHost、RuntimeDirectory、ProductionRuntime、
  preparation reset：`83 passed`。
- `git diff --check`：通过。
- AR2-7 verifier：1987 modules scanned、200 classified、93 migrated；`hashErrors`、
  `unclassifiedForwardDependencies`、`unclassifiedReverseCallers`、`bundleCrossLayerImports`、
  `dynamicReferenceErrors` 全空。
- 清册只追加既有 `ecommerce_baseline_assessment_discovery.py` 的 Host 只读分类，初始 hash
  `dec823fe...`；没有移动或修改该模块。

本波代码 hash：

- `scripts/a0v_s_released_retirement.py`：`f1d22e06d081cd4190cdabe4f51043edc8b14e7de8b4caf160ef4309f53bbe03`
- `scripts/a0v_t_replacement_install.py`：`73fb9bc85807be7aa9639906ceba64c2ce120f635cd80cf2ee46aab75b914e10`
- `scripts/a0v_t_interruption_recovery.py`：`b21460332a625aa53df21883754c2d810e5b89b0666bb44841862698759651d7`

## 结论与下一波

结论：`A0V_SC4_5L6Z_U_CLEAN_RECOVERY_CRASH_REHYDRATE_GREEN`。

这不是 A0-V 或最终经营闭环完成证明。下一波固定使用 S 的正式 detach Receipt 与 group62，
为 U 登记 successor，并以全新 operation/idempotency namespace 执行九路
prepare → pause → commit → validate → resume；切流完成且 U binding 推进后，才重建 P01-P12
selection/control/binding 和 disabled definition。旧 S/T generation、source control、snapshot claim、
经营参谋 occurrence 均不得继承。
