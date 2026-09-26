# W5CB4 P2f｜原批准 Plan 的内容 EvalContract 权威绑定（施工前）

## 复习与现场边界

- 231-5 §1/4/5 与 231-9 BG-04：真实内容产物先通过有来源的评估，再由人类 exact 评审；数字同事不能自行选择审核规则或批准结果。栖月汇产品方案要求模型建议绑定精确数据/策略/版本/证据，无 readiness 则失败关闭。
- P2e `1c0d1603` 已使内容报告的 `gatePolicyRef` 只能等于冻结 EvalContract exact ref；这只是 Eval 输入与报告门。`ContentTaskRunOwner` 创建的原 Plan 两步目前没有 `gateRefs`，生产当前亦无内容主体 EvalContract/Suite 或 Artifact。不能以 P2e 的隔离夹具推断当前实例具备评审权威。
- 本小步不读商城源、不启 worker/Provider、不跑生产 Eval，不给旧 12 Run 重发，不在现有已批准 Plan 上补字段。m1 单写、不 push；生产元库 `a0v_092` 与代码迁移 `a0v_105` 不一致，禁止声称生产可运行。

## 文件级清单和串行步骤

1. 只读审 `aip_content_contracts.py`/`aip_content_draft_readiness.py`、内容 Skill 的正式 Publication/ReleaseGate 路径、`aip_production_contract_store.py`、`ecommerce_content_taskrun_owner.py` 与分析阶段 `ecommerce_analyst_stage_review_command.py`；证明内容审核合同的当前来源，区分生成模型自己的 EvalContract 和产物审核 EvalContract。若无正式来源，只记录缺口，不从任意 READY 合同推断。
2. 先加 RED：原 Plan 的 `content_review` 必须有且仅有一个 exact 内容 EvalContract；无 ref/重复/错类型/错租户/旧 revision/hash/未冻结、未 READY、错误 subjectKind/inputMode、未正式发布 Skill 或 ReleaseGate 失效时不能形成待办/Report/ReviewIssue。已有原 Run 没有 gate 不得被事后补票；`dev-org/dev-project` 零 canary。
3. 最小实现优先做只读 Plan gate authority reader，复用 AIP 合同、Suite、Publication/ReleaseGate 与计划快照，不新建审核表；只有能从**当前正式内容审核包**在 Plan 创建前得到 exact ref，才把它作为 `content_review.gateRefs` 写入新 Plan。若正式包尚未就绪，新内容 TaskRun 的 claim/execute 必须失败关闭且不消耗 one-attempt；保留旧 Run 状态，不回滚已发生的 Provider 结果。
4. 专项及邻近累计回归、隔离 PG schema/租户与重复消费检查；若涉及页面再做浏览器验收。复审与 P2e、231-5/231-9 一致性，verification 单独落盘、精确提交。AOS/Prime 记忆标注代码门与真实实例缺口，不能写成自然链 GREEN。

## 退出条件与下一段

- P2f 只在“原批准 Plan exact 绑定＋当前权威读回＋拒绝所有伪权威”后完成。随后 P2g 才实现已结算内容 Artifact/最新 StepRun/同主体 EvalReport 的有界待办与公共 ReviewIssue 人工决策；没有真实可读 Artifact 或合法 Eval 权威时待办为空，不手造审批。

## 第 1/4 步审计结果与施工顺序修订

- 2026-09-26 只读元库 `aos_meta_head`：head `a0v_092`，`org-org/dev-project` 的 `subjectKind=ecommerce_content` EvalContract 数为 0；C06 Skill revision 1 为 evaluated，revision 2/3 为 published，C06 现有 Suite 只有 `ecommerce.skill.C06.contract.v1@1`。该 Suite 是 Skill 隔离治理评测，不是当前可读内容 Artifact 的主体评测。`ContentPipelineRefs.evalContractRef` 仅为消费端输入，`AipContentDraftReadinessService` 只验引用存在，二者均不构成 Plan 创建前的正式内容审核合同来源。
- 分两段施工：P2f-a 先让现有 ReviewIssue/Host 对原批准 Plan 的 exact `content_review.gateRefs` 失败关闭，防止历史/外部报告绕过批准 Plan；此段不声称具备正向生产权威。P2f-b 再形成面向 `ecommerce_content` 的正式 Suite、发布/ReleaseGate 和冻结 READY Contract 的受控来源，并在**新** Plan 创建前绑定；只有它们全链 exact 证明后才考虑自然评估。不得改写旧 Plan、拿 C06 Skill 治理 Suite 或模型生成 EvalContract 顶替产物审核。
