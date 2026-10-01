# BG00GT 首次模型评测授权增量方案（待裁决）

基线 AOS-001060 / m1 19f8c70b。Task W5CB4-BG00GT-BOOTSTRAP-DESIGN-20261001。本文件是方案与源码调查，不是已实现或执行批准。

## 1. 复习与可复核事实

- 上位231-5：任何外部调用必须有当前批准；先预留费用，unknown只读对账；必须真实产物、评审、回流。
- AIP22 §5.2规定SDK、AgentRun、试聊、TAOR、Logic DryRun、Eval共用一个resolver；§4普通运行要求active Model/Route与exact Eval通过。
- `aip_model_runtime_resolver.py:resolve/_candidate`：route_not_active、model_not_active、route_eval_gate_not_passed、model_eval_gate_not_passed均阻断。
- `aip_exact_provider_invoker.py:__call__/_validate_composition`：READY以及Model/Route/Policy/Provider全部active才可解析secret并调用transport；不得构造假的READY对象绕过。
- `aip_llm_adapter.py:chat_exact`沿上述resolver，未发现首次模型评测专用授权入口。
- `aip_eval_contracts.py:EvalExecutorCertificate._purpose_and_time`仅允许SkillTemplate target；`aip_eval_writer_atomic.py`和writer preflight均为Skill专用，不能用改枚举冒充Model可执行身份。
- `aip_eval_runner.py:run`有target/judge callback执行，随后写Report；`aip_release_publication_service.py:derive_gate`核验Report/Run/Suite。callback返回值本身未证明Model实际执行、供应商回包与费用，不可把它当正式模型来源。
- BG00GS只读候选已给出sourceRef/headVersion及下一active targetRef，executionAllowed=false；可作为审批输入，不可直接授予执行。

结论：首次质量评测需要在“尚未通过质量评测”的模型上进行受控调用。现有普通业务入口不承担此权限。不能关闭Eval检查、塞入假Gate、复制已通过模型、手工造Run，或启用未授权Provider来打破循环。

## 2. 提请裁决的增量边界

建议在原AIP-4/AIP-7控制面增设**评测用途授权**，仍复用同一resolver及Provider transport。业务运行条件保持原样；评测用途只能消费经过独立审批的精确候选，不产生业务运行READY。

此裁决只授权后续代码与隔离验证，不授权当前真实库写入、Secret读取、Provider调用或部署。涉及权限语义增量，依aos-engineering-delivery方案门，确认后才能编码。

替代方案：维持现有全部调用须先通过Eval的规则，首次模型评测只能等待另有正式、可验证的外部评测结果接入方案；当前不能假定有这样的结果或入口。

## 3. 拟实现的端到端合同

1. 评测申请冻结tenant、sourceRef/headVersion、next-active targetRef、Suite/Dataset/Case/Judge refs、Provider/plugin/Secret版本、Policy/Quota/Price/Budget refs、输入对象hash/数据分级、调用数及token/费用上限、截止时间；客户端不得自报passed或READY。
2. 原Action maker/checker独立审批；批准绑定完整申请hash与版本，改配置/撤销/到期即失效。读取候选不得生成批准。后续实现先确认预算/容量公共owner能接受EvalRun主体，禁止造业务Task/AgentRun满足旧接口。
3. 同一个resolver新增明确评测用途验证方法，回读当前head与候选、全部非质量运行依赖和评测批准；只返回单独的评测准入合同。不能新增skip_eval、trust_client、force_ready开关；不能让评测合同传入普通chat_exact。
4. 原Provider传输与Secret backend复用；原子固定invocation key、独立预算/容量预留、持久化发送意图，事务外执行。每个用例有限次且默认不自动重发；发出后unknown保留占额，只读对账。守护重试不得重发业务请求。
5. Model/Route Target executor及Judge身份分别绑定精确目标与purpose；真实响应/Usage/费用和签名执行Receipt才进入原EvalRun→Report→Gate生产链。复用表/Owner优先；新增许可及执行状态如确实无现存owner才做additive migration。
6. 先Model评测→通过后追加active Model→更新Route候选引用→Route评测→通过后追加active Route。禁止用仍引用validated Model的旧Route候选冒充最终运行路由。
7. Gate绑定实际next-active目标；发布时再次CAS及重验依赖与批准，目标变化须重新评测。普通业务运行仍要求该exact Gate和其余原门。

## 4. 文件级施工顺序（裁决后登记各波精确Lease）

| 顺序 | 拟触及文件 | 完成判据 |
|---|---|---|
| GT-a | 新`aos_api/aip_model_eval_authorization.py`；`aip_model_runtime_resolver.py`；对应`tests/aip/test_model_eval_authorization.py` | 明确评测准入合同与唯一依赖回读，不能当普通READY；无外部调用 |
| GT-b | 原`aip_action_*`批准绑定、`aip_budget_reservation_*`/容量owner；新评测申请owner及必要additive迁移（编码前精确登记路径） | 原maker/checker/CAS/幂等批准，无手工审批、无伪业务Task/Run |
| GT-c | `aip_exact_provider_invoker.py`、`aip_eval_runner.py`、`aip_eval_contracts.py`及原签名证据owner | 共用真实transport；发送意图/unknown对账；原业务入口不接受评测许可 |
| GT-d | `aip_release_publication_service.py`、原Eval reader/writer | Model/Route报告与Gate必须有实际执行及Usage/费用证据；撤销、来源漂移拒绝 |
| GT-e | 原`routers/aip_model_runtime.py`、Web `api/aipModelRuntime/`和`pages/s2/aip.tsx` | 页面申请/审批/评测状态与后端一致；无假READY、无发现目录fallback |

具体新增文件在各子波写入Task/Lease前确认；不以本表授权批量修改原Owner。上位方案AIP22需追加评测用途与普通运行用途的明确边界，不重写架构。

## 5. 验证门

- RED：未批准候选、跨租户、maker自批、错head/hash/目标、过期撤销、未知价格、预算不足、Secret版本漂移均不触及transport。
- 正向：在隔离PG经原配置生产与真实签名批准到评测意图/预留，再经过有证据的执行结果生产Report/Gate；测试double只验证协议，不能算真实Provider验收。
- 故障：每个提交/发送/落证据边界中断，证明不重发unknown、预算不误释放；原普通业务路径回归保持active+Eval要求。
- 发布：Model→Route顺序与CAS/hash严格一致，旧候选无效；真实provider验收另需当前正式授权、可恢复备份与克隆恢复门。
- 浏览器：申请、审批、待评测/失败/unknown/通过状态与后台一致；正向业务证据必须来自真实实例。

## 6. 当前进度与继续入口

GT第2/9步：源码与上位方案核对完成，权限语义增量待裁决，未写生产代码。与其独立的Review→TaskRun→AgentRun来源检查可继续；其正向首链仍需模型运行门。Goal保持active。watchdog仍仅方案未部署。

## 7. 独立来源链检查结果

- `tests/extension_runtime/test_ecommerce_content_taskrun_owner_pg.py:seed`直接插入Review运行Receipt及TaskBrief；只证明intent边界，不是原Review producer自然输出。
- `tests/extension_runtime/test_ecommerce_content_agentrun_owner_pg.py:accepted_taskrun`直接插入approved Plan/running TaskRun，再调用intent ack；不能用其作为真正Review→TaskRun验收。
- `tests/aip/test_content_first_action_binding_pg.py:prepared`明确替换`ContentBudgetCommandOwner._prepare_approval_sources`与source_envelope；真实Action批准测试不证明上游自然来源齐备。
- 原`ContentBudgetCommandOwner._prepare_approval_sources`要求合法当前capacity/budget intent（pending0或claimed1），再回读完整来源。因此后续联合测试必须从原Review producer开始，不能以手工intent/Run填补。

独立下一动作：建立原Review producer输入清单，沿真实AnalysisReceipt、GrowthPlan、ReviewIssue、EvalReport和artifact来源逐项接线；到模型权限边界即保持该实例禁入，不能用历史测试种子跨过。以上文件只读，未运行独立opt-in PG测试、未设置AOS_EXTENSION_PG_TEST。
