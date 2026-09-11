# 经营参谋阶段评审运行 exact 纯规则方案

日期：2026-09-12

基线：`7322a6dc`

状态：实施完成，宿主 current 运行装配待办

## 宿主运行审计

`ecommerce_analyst_stage_review_runtime.py` 读取当前 Task/Plan/Run、最新 StepRun、Checkpoint、
依赖快照与 Evidence，并核验状态机、撤销和内容 hash。依照单写者与权威边界，这些查询、锁、
当前性和哈希证明必须留宿主，不能复制到包内。

可迁移部分仅是无存储的领域形状比较：阶段到 subject 类型/观察字段的映射，以及已由宿主验证
的 exact 引用与观察正文是否相互一致。

## 本波目标与合同

- `require_stage_runtime_references` 只接受 portrait、diagnosis、solution-design；taskRunId 必须规范
  非空，planRef 必须是 PlanRevision，stageAttemptRef 必须属于同一 TaskRun 且 stepKey 精确等于
  stage，subjectRef 必须分别为 InsightRevision、DecisionSummaryRevision、GrowthPlanRevision。
- runtime 的 solution-design 只接受连字符拼写；DTO 为历史 Eval 兼容的 `solution_design` 在运行
  当前链中继续 fail closed。
- `require_observed_stage_subject` 要求宿主已验真的 Evidence payload 绑定同一 stepRunId、stepKey，
  内层 payload 为对象，且 `insightRef`/`decisionRef`/`growthPlanRef` 等于 exact subject JSON。
- 两个函数不验证 Run/Task/Plan current、step 状态/顺序/inputHash、Checkpoint、依赖快照、
  Evidence hash/revocation/marking，也不访问 TenantScope 或数据库。
- 不修改宿主生产文件、Candidate、OCI、Registry、Installation 或 operation。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_runtime.py` | `6e8bd4e0bb827e550e97c7fbc15a38f8531da6cfe529e020c1b342ade4d4bf36` | 验证输入；宿主权威运行检查不改 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_runtime.py` | new | exact 引用与观察正文纯比较 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_runtime_rule.py` | new | 三阶段正负合同与隔离 import |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `5af80c431b905038be6fdef868f4d41649d53403d4cdad9a037d2675c2149004` | 登记 9.15 切片 |

## 退出与下一门

三阶段 exact 引用/观察正例、字段与拼写漂移、错误 subject/step、独立 import、相邻包和宿主
runtime 合同、编译与 AR2-7 closure 全绿后提交。下一波审计 stage eval report 的无权威 DTO/
比较切片；第 9 节整体仍 PENDING。
