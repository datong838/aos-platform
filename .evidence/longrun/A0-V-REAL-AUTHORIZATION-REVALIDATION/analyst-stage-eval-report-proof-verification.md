# 经营参谋阶段 Eval 报告最小证明验证

日期：2026-09-12

基线：`00d1502a`

结论：阶段评审所需的最小 Eval 证明与 exact 输入比较已进入 growth 包，完整 Eval 权威仍留宿主。

## 核对与验证

- report 必须是 EvalReportRevision exact ref、gatePassed=true，cutoff/createdAt/可信 now 均带时区
  且 `cutoff <= createdAt <= now`。
- tenant、subject Artifact、StepRunAttempt、EvalContract、GatePolicy 与 cutoff 任一漂移均拒绝；
  布尔值不能冒充 exact revision。
- 本波、stage runtime/command/decision 包及宿主真实 PostgreSQL 报告/runtime 合同：`104 passed`。
- 独立进程阻断 `aos_api` 后导入通过；编译和平台 import 扫描通过。
- AR2-7 closure：扫描 1772，分类 135，迁移 93，全部错误数组为空；提交前 diff check 必须通过。

## 一致性与风险

实现没有复制平台通用 EvalReport，也没有把 passed 投影当作 latest 或执行权限。宿主尚未调用包内
证明，完整 Report/Run/Suite/Gate 当前链和 1.5.0 安装装配仍待完成。下一波进行评审链宿主装配
审计，确定最窄可信端口接线顺序。
