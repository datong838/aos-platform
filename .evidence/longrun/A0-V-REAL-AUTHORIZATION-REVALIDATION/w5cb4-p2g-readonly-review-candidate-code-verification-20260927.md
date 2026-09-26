# W5CB4 P2g 第 3 段｜只读内容评审候选内核（部分代码门）

## 范围与证据强度

- 依据 231-5 §1/4/5/7、231-9 BG-04 与 `w5cb4-p2g-content-subject-eval-review-pending-plan-20260927.md`，新增内部读取器；**没有 GET 路由、没有创建 EvalRun/ReviewIssue、没有真实候选同库正向验收**。不可据此称人类待办已可用。
- `ecommerce_content_review_pending.py` 在一个租户只读事务中复用已结算结果/Provider/Usage/Artifact/Task/Brief 的来源读回与四相 checkpoint，复核当前内容操作 Receipt 对 dispatch/runtime binding 的 exact 同代关系、当前内容 EvalContract、原 Plan gate、最新 succeeded 生成步骤、唯一通过的同主体报告及其 EvalRun 绑定。无报告返回 `None`，多义、旧安装、缺权威、漂移失败关闭；已有同 Artifact Issue 时不重复列为待创建候选。此快照不是 POST 的授权，后续写入仍须重验完整安装锁。
- RED：模块不存在导致新专项无法收集。GREEN：无报告空态、旧 dispatch、缺 gate、多报告、可信 scope、通过/失败报告、重复只读等 7 项单元契约通过。内容＋通用 EvalRunner 累计 **283 passed, 9 skipped, 7 warnings**；`git diff --check` 通过。9 skipped 为专用 PG opt-in，单元假连接也不当作真实同库正向证据。无 UI 变更，浏览器验收不适用。

## 余险与下一步

- 当前实例之前只读为 `a0v_092`，无当前预审 Graph/合同、内容主体报告；未迁移、未注册、未启 Worker/Provider。候选读取器未接公开 API，因此运行端仍默认关闭。
- 下一步：用一次性隔离 PG 从正式已结算 result、Provider/Usage Receipt、可读 Artifact、succeeded StepRun/checkpoint、正式当前内容合同和同主体 EvalReport 组合正反证明；特别核租户隔离、当前安装漂移、Report/Run JSONB 绑定及重复读。若组合证据不成立先修读者，不暴露 GET，更不能造人工 Issue。之后才接公共 ReviewIssue 创建及人类决策。
- 未触碰商城源、原 12 Run、230 L0、外部发布；`dev-org/dev-project` 只作零 canary，m1 单写、不 push。
