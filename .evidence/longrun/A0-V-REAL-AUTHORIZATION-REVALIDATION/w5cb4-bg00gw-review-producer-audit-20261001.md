# BG00GW 原 Review producer 来源调查与施工入口

基线 AOS-001063 / m1 b20948c2。Task W5CB4-BG00GW-REVIEW-PRODUCER-AUDIT-20261001。
进度为开发第 2/9 步；本次仅完成来源调查，未完成实现、联合测试或业务验收。last GREEN 保留 BG00GV。

## 上位要求与范围

复习 231 主计划 7.2/7.3/14、231-5 全文、231-9 评审和交接合同，以及上下文 456。
自然分析→人工决策→原 Handoff→Task/Brief→TaskRun/AgentRun 必须保留当前真实来源，不能靠直接 INSERT、手工 Run 或测试替身补输入。本波真实库访问 0、商城源读取 0、Provider 调用 0；不修改执行权限，不部署 watchdog。

## 已读原 Owner 与实际依赖

| 输入 | 原生产/消费入口 | 本次核实 |
|---|---|---|
| GrowthPlan draft | ecommerce_analyst_growth_plan_receiver.receive | 依赖 succeeded D03 attempt、Provider/Usage Receipt、原始 agent_text_output 及当前 Insight/Decision 来源；不能用构造 draft 替代生成 |
| approved GrowthPlan | ecommerce_analyst_growth_plan_approval.approve | 原 current draft/CAS/receipt/priorRef 追加 approved；直接调用该服务不证明外层身份授权 |
| 阶段人工决策 | ecommerce_analyst_stage_review_command._sources_and_eval | 消费原 agent_text_output、原 generation query、当前阶段 EvalContract、Skill target、exact EvalReport、责任人及 Plan |
| 阶段 Eval | aip_business_investigation_eval.evaluate_stage / aip_eval_runner.run_by_contract | coordinator 使用原 runner；runner 明确拒绝 SkillTemplate target，而阶段来源校验明确要求 D01/D02/D03 SkillTemplate。不能换成 logic_graph 假装接通 |
| 正式签名 Skill 报告 | aip_eval_writer_atomic.persist_signed_skill_eval_report | 原子 SQL 未保存 eval_contract_ref / subject_artifact_ref / stage_attempt_ref / gate_policy_ref / evidence_cutoff_at；其现有输出不能直接满足阶段 reader。未据此扩大 writer 权限 |
| ReviewIssue | coordinator.open_review_issue → production store.create_review_issue | 自动 open 只允许 gatePassed=false；质量通过后返回 request-human-stage-decision。该路径没有自动创建一个供旧 Handoff 使用的 OPEN Issue |
| Review→Handoff | ReviewAdvanceHostService / 包 ReviewHandoffRequest | 需要 current approved GrowthPlan、OPEN ReviewIssue、EvalReport、同 TaskRun 四类 portrait/diagnosis/growth_plan/evidence_summary Artifact；Issue subject 必须属于四类之一 |
| Task/Brief | ReviewAdvanceHostService._review_lineage | 原 AipTaskStore 与 TaskBrief Owner 写入；直接调用私有方法跳过上游校验不能证明整链 |

## 改变下一动作的发现

1. 阶段来源合同与旧 Handoff 合同存在实际错位：阶段决策绑定原始文字 Artifact 和 AnalystStageDecisionRevision，旧 Handoff 必填 ReviewIssueRevision 及四类业务 Artifact。将文字 Artifact ID 填入四类 binding 会被 artifact_type 校验拒绝；改名或补 INSERT 会伪造来源。
2. 即使模型先运行成功，阶段评测也还有独立接线缺口：现 generic runner 拒绝 Skill target；签名 writer 的 INSERT 未携带阶段绑定。模型 bootstrap GT 方案不能自动解决这个缺口。
3. `open_review_issue` 的失败问题语义不能拿来代表所有人工批准。质量通过路径必须追原阶段决策，不能为通过报告自动造 error Issue。

以上是已检查入口之间的合同事实，不宣称仓库中绝无其他可用路径。下一步先核对现有 compile-only Handoff bridge 与 stage decision store，寻找可复用的正式适配点，避免另建审批权威。

## 文件级下一施工卡（尚未授权变更公共合同）

| 顺序 | 精确调查/候选文件 | 必须先锁定的验收 |
|---|---|---|
| GW-a | aos_api/aip_eval_writer_atomic.py、aip_eval_writer_authority_preflight.py、aip_eval_report_proof_reader.py、ecommerce_analyst_stage_eval_report.py | 原签名执行输入是否已经绑定原始文字/阶段/合同；若扩展，五项必须全有或全无，签名/Run/Report同源，无删门 |
| GW-b | aos_api/ecommerce_business_investigation_handoff.py、ecommerce_analyst_stage_decision_store.py、ecommerce_growth_runtime_adapters.py；包 ecommerce_business_investigation_review_command.py | 由原 current accepted solution decision 导出 Handoff 的完整来源，不创建假 ReviewIssue；旧失败问题/退回路径保持 |
| GW-c | 原 tests/extension_runtime/test_ecommerce_review_issue_eval_authority_pg.py、test_ecommerce_content_generate_handoff_lineage_pg.py 及对应新联合测试（开码前登记路径） | 从原生产者到 Task/Brief/intent 的真实隔离联合；明确哪些源仍为 fixture，不计当前首链 |

公共合同或权限语义改变必须先完善对应方案并评审。本卡不授权实现 bypass/skip_eval、新签名用途或当前实例调用；GT 模型首次 Eval 权限裁决与正式 OIDC/API 身份问题仍独立待答。

## 验证与限制

- fresh memory-status：AOS-001063，七 strong CURRENT；memory-validate exit0/GREEN，1526 Delivery、1524 Task、4058 events（本 Task 登记前）。
- 原源码通过 Python AST 解析，9 个文件、15 个函数定位与 SHA256 记录于同目录 w5cb4-bg00gw-review-producer-sources-20261001.json。记录含基线 full HEAD，可逐项重算，不含凭据或业务数据。
- 本次没有代码变更，因此没有 RED/GREEN 或浏览器正向验收；不把源码调查计为完整开发 9/9。
- 若干定位命令因猜测旧文件名或 zsh glob 无匹配报错，已改用 rg --files/实际源码定位；不将查找失败当功能不存在的依据。
- 起初文件名搜索范围过宽，列到了工作区其他目录文件名，未读取其内容；后续限制 aos-platform 和 docs/palantier，禁止再次扩到商城源。
- 当前库118、代码130与尚未重启的描述来自 GV 已存证据，本波未重测服务，不能标为本波实测。

## 下一波与收口

优先 GW-a 原签名报告与阶段绑定输入合同审查，再 GW-b 原阶段决策到 Handoff 的适配；这两项可以独立于真实 Provider 授权先完成设计与代码依赖核对。正式 OIDC/受限 API 身份到位后回 GU/GV 的独立恢复波，完成零窗口/第二备份/当前迁移与重启。GT 裁决后推进模型评测用途代码；现阶段不调用真实 Provider。
本调查更新 AOS/Prime/457 与 D-waves，精确 m1 提交，不 push；Goal 未完成且保持 active。
