# 经营参谋阶段评审运行 exact 纯规则验证

日期：2026-09-12

基线：`7322a6dc`

结论：阶段运行 exact 引用和已验真观察正文的纯比较已进入 growth 作者包；当前运行与 Evidence
权威继续留在宿主。

## 实现核对

- portrait、diagnosis、solution-design 分别匹配 InsightRevision、DecisionSummaryRevision、
  GrowthPlanRevision，并要求 PlanRevision 和同 TaskRun 的 StepRunAttempt。
- runtime stepKey 必须精确等于 stage；历史 Eval DTO 可接收的 `solution_design` 在当前运行链中
  继续拒绝，未扩大兼容边界。
- 观察正文必须绑定同一 stepRunId、stepKey 和对应 exact subject JSON。
- 布尔 attempt、错误 Plan/subject 类型、跨 Run、错误 step 和观察正文替换全部 fail closed。
- 包没有复制 Task 状态机、Checkpoint/依赖哈希或 Evidence 撤销与内容校验。

## 验证结果

- 本波、前三个评审包切片和宿主真实 PostgreSQL runtime/command 合同联合测试：`135 passed`。
- 宿主三阶段真实 checkpoint、前序完成、后继未启动、租户隔离与 exact subject 回归通过。
- 独立进程阻断 `aos_api` 后可导入；Python 编译和平台 import 扫描通过。
- `verify_closure.py --phase ar2-7`：扫描 1771，分类 134，迁移 92；所有错误数组为空。
- `git diff --check`：提交前执行并要求通过。

## 方案一致性与风险

实现仅迁移产品领域映射，不复制平台安全状态机，也没有把观察 Evidence 当成自动执行权限。
主要剩余风险是宿主 runtime/command 尚未调用包内规则，Stage Eval report 的合同与读取仍未迁移，
1.4.0 安装不含该实现。下一波审计 `ecommerce_analyst_stage_eval_report.py` 的 DTO 与纯比较边界。
