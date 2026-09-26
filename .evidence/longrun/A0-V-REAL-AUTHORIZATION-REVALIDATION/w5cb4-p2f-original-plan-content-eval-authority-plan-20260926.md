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

## P2f-b 评估包方案定稿（编码前）

- C06 当前逻辑要求输入中已有 `factuality_state=passed` 等状态；当前可读内容 Artifact 没有这些独立审核事实。直接把 C06 治理 Suite 用作产物 Eval 会循环论证。首个正式 Eval 定义为**供人工评审前的结构/来源完整性门**：检查正文、商品/渠道、事实来源、约束核查均存在且与原 Artifact 哈希/生成 attempt 同源；只输出能否进入人工评审，不输出“事实正确/合规通过”结论。事实、敏感信息、禁用表达和格式的实际判断由人类 exact ReviewIssue 决策。失败报告不能被 Host ACCEPT。
- 复用 AIP 可发布的 `LogicGraph`，在图的输入 schema 与纯表达式 `transform` 中实现确定性 completeness 判定；无 LLM/Tool/Action。发布门只能针对确有持久版本/哈希的 Graph，不能用未登记的代码常量冒充 target。新 Graph 的 EvalSuite 应有正向、空正文、缺来源、错商品/渠道等隔离用例；在发布门与 Publication 后才创建/冻结 `subjectKind=ecommerce_content`、`subjectInputMode=ecommerce-readable-content/v1`、`requiresHumanDecision=true` 的 EvalContract。批准合同只证明结构门可运行，不替代每篇内容的主体 EvalRun。
- 文件顺序：`services/aos-api/aos_api/ecommerce_content_pre_review_eval.py` 定义 Graph 请求、输入/结果边界与确定性执行；`services/aos-api/tests/extension_runtime/test_ecommerce_content_pre_review_eval.py` 先 RED 覆盖正/负与无外部调用；受控注册脚本/Owner 后续另加，复用 `LogicGraphStore`、`AipEvalPackRegistry`、`AipReleasePublicationService`、`AipProductionContractStore`，不得直写其表。`ecommerce_content_taskrun_owner.py` 仅从当前唯一已发布/未撤销的此 Graph 对应冻结 READY 合同选择并在新 Plan 创建前绑定；选择为零/多义/过期一律在 claim 前停，不消耗 one-attempt。
- 先完成纯 Graph 规格和执行专项测试，再做隔离 PG 的 Suite/Release/Publication/Contract 正向证明与错租户/撤销反例；未能证明完整正式来源时 P2f-b 保持未完成，生产元库不迁移、不注册、不启 Worker。将候选包升级和真实安装留到精确签名/安装波次，不修改既有冻结 1.11.0 候选包。

## P2f-b 第 1/4 步状态

- 已实现仅用于隔离用例的草稿 Graph 构造及只读执行函数；Graph 只有 input/transform，无外部 effect。对空正文、缺商品/渠道/来源/约束、错误封套/Artifact 引用、篡改 Graph 均失败关闭。
- 此步不是正式 Eval 权威：尚无隔离 PG 的 Suite、ReleaseGate/Publication 和冻结 READY 内容 EvalContract；不得把 helper 输出视作生产可接受报告，也不得创建自然 Plan gate 或开启 Worker。
- 下一步：在 AIP 正式注册／发布路径上做隔离 PG 正反用例，证明 Graph/Suite 与 exact subject 输入、当前发布权威一致，再处理 Owner 的原 Plan 创建前绑定。

## P2f-b 第 2/4 步接口复核与文件级修订（编码前）

- `AipEvalRunner.run` 对 `subjectKind=ecommerce_content` 会把 Suite case 的 input 替换为该次 exact Artifact 的内容封套。因此治理发布用的正/负多例 Suite 与未来每篇内容的主体 Eval 必须分别证明：前者证明 Graph 规则可发布，后者证明当前 Artifact/最新 attempt 在冻结合同下被评估。不得拿治理用例通过冒充某篇内容的通过。
- `AipProductionContractStore._eval_blockers` 目前只独立查 Suite ref、Publication、ReleaseGate 存在/有效，未交叉校验三者 target/suite 的 exact 同一性。P2f-b 的来源读取器必须额外核对同一 Graph id/revision/hash、同一 Suite、发布事件及门决定，并拒绝不一致；先不改变无关旧合同的全局 readiness 语义。
- 本段先在 `services/aos-api/aos_api/ecommerce_content_pre_review_eval.py` 增加持久 Graph target 的只读执行入口，要求 `AssetType.LOGIC_GRAPH`、目标 id/revision/hash 与持久快照一致，Graph 内容与代码审定规格一致，且执行结果只输出布尔值；拒绝未持久、篡改、错目标、失败或 effect 节点。`services/aos-api/tests/extension_runtime/test_ecommerce_content_pre_review_eval.py` 先 RED 覆盖。随后再以隔离 PG 的正式 registry/runner/release/contract API 形成新权威，不对当前实例写入。
- 进一步核查 `AipEvalRunner`：若同一 Suite 含正/负治理用例，真实内容主体运行时每个 case 都被同一篇 Artifact 封套替换，不可能同时满足正/负预期。因此需要**两份** exact Suite：治理 Suite 含正/负用例，用于 Graph ReleaseGate/Publication；主体 Suite 只含“该篇内容结构完整=true”的一例，用于 EvalContract 和每篇内容 EvalRun。两 Suite 的 target 必须为同一 Graph exact id/revision/hash；合同的 publication/gate 应绑定治理 Suite 的通过证据，而合同本身绑定主体 Suite。不得错误要求两 Suite ID 相同，亦不得让治理报告替代主体报告。

## P2f-b 第 2/4 步中间状态

- 已增加调用方提供的 Graph 快照与 target exact 对齐的无 effect 执行入口，并在一次性测试 PG 通过 `LogicGraphStore.create/get` 读回。它还未自行回读 Store/Publication，因此不能作为生产当前权威选择器；正式调用方必须先按同租户从 Store 读取并另验当前 Publication/ReleaseGate。
- 下一段集中接 AIP registry→governance Eval→ReleaseGate/Publication→冻结 READY 合同与错租户/撤销反例；只有全链同一 exact Graph target、治理/主体 Suite 各自正确绑定的交叉证明后，才可使 Owner 新 Plan 使用 exact gate。

## P2f-b 第 2/4 步隔离正式 API 证明

- 已用一次性隔离 PG 经 `LogicGraphStore`、`AipEvalPackRegistry`、`AipEvalRunner`、`AipReleasePublicationService`、`AipProductionContractStore` 串起治理 Suite 正/负 5 例→报告→发布门→Publication，另建主体 Suite→冻结 READY 内容 EvalContract；撤销后合同动态 BLOCKED，`dev-org/dev-project` 对相关 Suite/Contract 仍为零。
- 这只是隔离正式 API 的合同可行性，不是当前实例正式注册，也不是对任何真实内容 Artifact 的主体 Eval。后续仍须生产注册的可重入 bootstrap/只读预检、跨 Suite 同 target 与 Publication/Gate 交叉读回、Owner 在新 Plan 创建前唯一选择；未完成前不启用。
