# W5CB4｜可读内容产物→人工 exact 评审→Run 终态／反馈续跑（施工前）

## 上位方案与现场

- 231-5 §1/4/5/7、231-9 BG-04 与栖月汇产品方案要求：真实可读内容产物先供人核事实、敏感数据、禁用表达和格式；人工 ACCEPT/RETURN 是业务决策，不由 worker 代批。ACCEPT 后同一 TaskRun 应有正式终态，反馈进入总控复盘及 Wiki 候选，不自动发布或触达。
- W5CB3 只达到隔离受控 Artifact 代码门。现有 `ContentReviewHostService`、`BoundEcommerceGrowthFeedbackPort`、`CurrentFeedbackConsumer` 已有 exact 评审/反馈合同；但缺少从 W5CB3 的 Artifact 自动形成**可供人评审的当前待办**、评审后 Run 终态到反馈的同库自然证明。不得把旧假 Artifact、PENDING 预算或开发者手填命令当审批。
- 生产 `a0v_104` 未应用；Worker/Provider 关闭，原 12 Run 与商城源读不在本波。无当前合法 Artifact 时只做默认关闭代码与受控验收，不补造真实审批。

## 文件级清单与顺序

1. 先审 `ecommerce_growth_runtime_adapters.py` 的 ContentReview Host、`ecommerce_growth_feedback_port.py`、`ecommerce_growth_feedback_consumer.py`、公共 TaskRun／ReviewIssue Owner 与 `apps/web` 现有工作台入口；逐一记录 Artifact Ref、ReviewerAuthority、ReviewIssue、Task/Brief、Run 终态的当前归属和缺口。禁止发明第二审批体系。
2. 优先给 `services/aos-api/tests/extension_runtime/` 新增 RED：同库 W5CB3 Artifact 被识别为唯一待人工评审项；仅人类当前授权的 exact ACCEPT/RETURN 可进入 Host，未决/过期/错租户/旧安装均不推进；ACCEPT 后原 TaskRun 终态及反馈段独立读回；RETURN 只生新内部目标、不重用旧 Provider 结果或自动再发。若已有代码覆盖，则只做组合回归及最小接线。
3. 仅针对 RED 暴露的断点修改相应 Owner／API／必要的最小 UI，默认关闭任何新 worker。专项、累计回归、完整 schema 隔离 PG；如涉及页面，必须浏览器验收。复审方案/代码一致性和不可越权副作用。
4. verification 落盘→m1 精确提交→D-waves/AOS/Prime 记忆更新。生产激活仍须先通过 W5CB2/3 的完整同库自然链及当前安装、审批、预算、来源、权限和独立 Receipt。

## 复审修订：先封人工决策门，再接终态

- 现场发现 `ContentReviewHostService._issue_authority` 目前只接受 `ReviewIssueStatus.OPEN`，因而它证明的是“待评审存在”，**不是人类已决策**。正式 `resolve_review_issue`/`return_review_issue` API 才检查评审角色并写不可变事件；必须要求当前 issue 的 `resolved`/`returned` 终态与同 issue 的对应人类事件、版本、actor、payload 和 exact Artifact 一致，才能由 Review Host 产生业务 Receipt。不得把责任槽 `ReviewerAuthorityRevision` 单独当人类批准。
- 退回命令的业务 phase `content_generation` 与公共 TaskRun 步骤 `content_generate` 是两种不同标识；公共 `return_review_issue` 必须接实际 step key，Host 回馈继续保留业务 phase。明确映射，不全局改既有 Plan step key，也不降低 ReturnDecision 的当前 Run/版本/attempt 检查。
- W5CB4 分 P1/P2：P1 先做上述人类决定/退回映射的 RED→GREEN 和邻近测试；P2 再做 Artifact→待办、TAOR StepRun/TaskRun 终态及反馈同库自然接线。P1 通过绝不称本波完成，verification 只在 P2 或清楚记录未完成后落盘。

### P2 文件级入口与权威选择

- 公共 `AipProductionContractStore.create_review_issue` 强制已有 `EvalReportRevision`、ReviewRule 与 Artifact；不能为“让按钮可点”伪造 EvalReport 或建第二个审批表。先在 `services/aos-api/aos_api/aip_eval_runner.py`／`aip_eval_authority_store.py`、现有内容 EvalContract/Rule 种子中查可复用的**当前内容产物 Eval**；只有正式产出的 EvalReport 才能通过既有 Store 建内容 ReviewIssue。若当前根本无合格 suite/规则，应先实现并测试这一小块，且默认不启生产。
- `services/aos-api/aos_api/ecommerce_content_review_*`（仅确有断点时新增）负责从已结算的可读 Artifact 与原 TaskRun/Task/Brief/Plan、当前安装、EvalReport 组成有界待办投影；GET 只读、POST 决策沿既有 `AipProductionContractStore` 人类角色 API 和 Host exact Receipt，不给后台 worker 代批。
- `services/aos-api/aos_api/ecommerce_content_taskrun_owner.py` 或最小后继 Owner 只用公共 `AipTaskStore` 的 claim／TAOR evidence／complete_step／complete_run 达成正式终态；不直接 UPDATE Run/Task。人工 ACCEPT 才允许最后 Review step 完成，RETURN 由公共 ReturnDecision 派生新 `content_generate` attempt，不重发旧 Provider。反馈原 selector 已要求 succeeded/completed，受限写门保持不动。
- 前端仅在当前已有内容工作台缺待办显示/评审动作时改 `apps/web/src/components/workshop/ContentCampaignPage.tsx` 与相应 client/contracts/tests；页面需真实浏览器验收。每个分段先 RED，完整同库后才叫 W5CB4 通过。

### P2a 复审后的最小公共 Eval 扩展（先于 ReviewIssue）

- 代码核查确认现有 `AipEvalRunner` 的 subjectKind 只允许 `media_variant`／`agent_text_output`，而 W5CB3 Artifact 类型为 `ecommerce_content`；普通无 subject 的 EvalReport 不能证明评估了这个正文。先在 `services/aos-api/aos_api/aip_eval_runner.py` 为明确冻结且 READY 的 EvalContract 增加 `subjectKind=ecommerce_content`、`subjectInputMode=ecommerce-readable-content/v1`。只接受同租户 exact Artifact hash、原 Run 的最新 `content_generate` StepRun attempt、`ecommerceGrowthContentArtifact` canonical hash 与正文/来源字段完整性；提供 Eval target 的输入 envelope 必须绑定原 Artifact Ref，不可替代主体验证。
- 先在 `services/aos-api/tests/aip/` 加 RED：合法 exact 内容主体可进入现有 EvalRunner；跨租户、旧 attempt、错类型/哈希、空正文/来源、非冻结或模式不符的合同均 fail closed。只扩展通用主体校验与输入组合，不写特定商城数据、不自动注册或启用 suite。
- 产出的 `EvalReportRevision.subjectArtifactRef`、stage attempt 与 gate policy 才可被后续内容 ReviewIssue Owner 接受；若公共 ReviewIssue 当前仅验报告存在，应在内容路径追加同主体报告绑定检查，不能用无关 EvalReport 充数。
- 当前 `EvalGatePolicyRef` 名义类型仍固定 `MediaGatePolicyRevision`；本段只验证 EvalRunner 对 content 主体的能力，不把测试中的 `fixture-policy` 当实际内容 GatePolicy。正式内容 EvalContract／Suite／GatePolicy 注册与 exact 当前权威是后续激活硬门，必要时先做通用 Eval 合同的增量，而不是把媒体政策冒充内容批准。

### P2c 当前权威与待办 Owner 文件级细化（P2b 后）

- 复审结果：`ecommerce_analyst_stage_review_command.py` 已有“原批准 Plan 的 exact EvalContract → 当前冻结 READY 合同 → Suite/Skill/ReleaseGate → 同 Artifact/attempt Report”的可复用校验范式；`ecommerce_analysis_startup_eval.py` 可按已发布 Skill 派生合同，但不是对当前可读内容的自动批准。W5CB3 内容 TaskRun 的 Plan 目前只有 `content_generate`、`content_review` 两步，尚未声明内容产物的 exact EvalContract；不能从任意现存合同或 fixture 推断生产可用。公共 ReviewIssue REST 路由已有 create/resolve/return，不新增审批表。
- 先补 `services/aos-api/tests/extension_runtime/` 的隔离 PG RED：已结算 `ecommerce_content` Artifact、最新生成 attempt、当前安装与原 Task/Brief/Plan、同主体 EvalReport 构成**一个**待办候选；无报告、错合同/主体/attempt、旧安装、错租户、未结算或原 Run 不匹配均为零候选。不得为了待办而生成报告或 Issue。
- 最小代码入口候选：`services/aos-api/aos_api/ecommerce_content_review_pending.py` 只读候选投影；必要时在 `ecommerce_content_taskrun_owner.py` 原 Plan 上持久化受控 exact EvalContract gate ref，但须先证明来自当前已发布内容 Skill 与 READY 合同。公共 `aip_eval_runner.py` 与 `aip_production_contract_store.py` 不再为页面方便而放宽。
- 内容 Eval 的生产激活另设硬门：先有经正式 Publication/ReleaseGate 的内容 Suite/Contract、当前受控 GatePolicy 类型/Ref、同原 Plan exact 绑定，再运行 Eval；`fixture-policy`、普通无主体 Report、仅有未冻结草案一律不认。若本轮只有代码门，待办 GET 返回空/明确 blocked，不虚构可评审项。
- 之后才接公共 ReviewIssue 创建与人类 resolve/return、ContentReview Host Receipt、TAOR 终态；最后读回反馈/总控/Wiki 候选。UI 改动必须随后真浏览器验收。本细化不启 worker、Provider、商城源读或外部 Effect。
- P2b 只封住**新建**内容 Issue；历史已存在或经其他入口留下的 Issue 仍可能被 Host 消费。先在 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py` 加 RED，再最小修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 的 `ContentReviewHostService._issue_authority`：按原 Issue exact report ref 回读报告与内容 Artifact/原 Run 的最新生成 attempt；无主体、错主体、旧 attempt、缺合同/政策均拒绝。已有人工事件和 ReturnDecision 校验不降低。此为 P2c 前置补洞，不能据此声称待办或生产 Eval 已完成。

## 退出／下一波

本波最多证明受控 Artifact 后的“待人评审→exact 决策→Run/反馈”代码链；没有真实人类审批不得声称自然闭环。下一波按本波证据补生产激活硬门与当前实例自然观察，而非回到旧 12 Run 的逐行补数。
