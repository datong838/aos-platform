# SC4-5L6Z-P：P occurrence 受控退役结果

日期：2026-09-17

## 结论

P installation `9950e057-5cb4-4849-a499-35837d8d0fb6` 的 Policy11 已通过新的 released
recovery 命令从 binding revision1/enabled 变为 revision2/disabled。event-control dispatch 已由
group revision49 推进到 revision50，只有 event-control route 被 fence；其余九路未被误 fence。

原失败自然窗口的 65 个 occurrence 已逐一通过正式
`UnacceptedAnalysisClosureReceipt` 关闭：5 个 expired unknown attempt 变为
`closed_unaccepted`，60 个 pending/unclaimed 没有伪造 attempt，65 个 occurrence 均为
cancelled。每条 Receipt 都声明 `businessAccepted=false`。目标 runtime command Receipt 和
BusinessInvestigationRun 仍为零，`dev-org/dev-project` canary 为零，外部副作用为零。

## 前向修复与真实发现

`a0v_076` 只修改两个既有数据库函数的 exact 片段：released event fence 可容忍严格定义的安全
expired unknown；verified released fence 可逐条关闭 expired unknown 或 pending/unclaimed。
主库在 advisory lock 内从 `a0v_075` 单步升级，13 张相关业务表的迁移前后指纹完全相同。

真实 disable 首次暴露 qualified owner 与外层 service 的 drain 判定不一致；事务在写入前回滚。
owner 随后采用同一安全 unknown 条件，新增组合测试保持 running、claimed、future/target authority
继续 fail closed。系统重启还使 Web 和 registration 连接环境失效；执行器改为从已验证 main
连接和既有 0600 registration identity 显式恢复，不再依赖终端残留环境。第一条 closure 的孤立
intent 已由 exact presubmit proof 证明发生在建连前，且数据库同键 Receipt 为零，才获准继续。

## 验证

- focused + 相邻 PostgreSQL/组合合约：58 passed；
- Python 编译、`git diff --check`：通过；
- AR2-7 closure verifier：扫描 1982 个 Python module，hash、正反向依赖、跨层 import、动态引用
  错误均为零；
- 独立真实回读：65 cancelled、5 closed_unaccepted、65 closure Receipt、零目标 Receipt/Run、
  零 canary。

## 尚未完成与下一波

P 仍是 released runtime 对应的已 fence 路由和 active installation。本结果不等于 uninstall，亦不
等于真实经营首链完成。下一波按既有生命周期执行 event shrink、九路 dispatch detach、installation
uninstall，并验证历史 Receipt 可读、当前路由不再指向 P、无租户越权副作用；完成后继续修复
source schedule 的陈旧 `last_run`，再恢复干净 successor 的自然触发窗口。
