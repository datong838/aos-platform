# BG00GW-b 完整阶段评测生产与消费接线方案

状态：待公共证明协议评审，未实施。基线 AOS-001066 / bd1d068e。Task W5CB4-BG00GWB-SIGNED-STAGE-DESIGN-20261001。依据231、231-1 N4/N5四层边界、231-5 §4/5/7及459。用户未授权Provider/Host启动；本方案不产生该授权。

## 1. 现场证据与修正

- 原包现在能由固定消息调用确定性结构评测；新消息只有结构结果，不生成正式Eval。
- EvalExecutionReceipt v1 的签名覆盖run/suite/case/target/input/output等，但没有subject、query、stageAttempt、contract、policy、cutoff；writer当前要求inputHash等于静态Suite case输入hash。GW-a只保证Report/Run元数据保真。
- read_stage_eval_report验证原Report/Run/current/source关联，没有直接调用signed proof reader；上游_release gate在SkillTemplate分支明确抛出formal Skill Eval executor authority unavailable。因此当前外层仍禁入；不是已证实可执行漏洞。
- 原AipEvalRunner也拒绝SkillTemplate。只删除两个拒绝分支会丢失正式执行权威，禁止这样接通。
- 现有target证书语义是执行exact SkillTemplate。把离线结构评测输出签成D01/D02/D03执行结果，会误陈述实际执行；为评测重新执行原生成Skill又可能重复费用或产生另一个正文，均不采用。
- 同目录probe.py实际生成测试专用Ed25519签名，原verify_execution_pair通过；模型六项上下文字段缺失断言成立。JSON记录七源码SHA和函数行号。无DB/网络；这是协议边界证据，不是真实经营验收。

## 2. 推荐决定（待评审）

新增有独立用途的“既有产物评测证明”协议，供当前阶段产物评审使用；保留v1 Skill执行证明全部语义。不得把新证明用于Model首次发布、Skill发布或运行许可。这里增加的是证明类型和消费规则，不是给当前实例补签、授权或创建Run。
不选择更改静态Suite inputHash为随每次正文变化的hash：那会让已批准Plan→Contract→Suite被迫每次变更，混淆规则批准和运行证据。

## 3. 完整信封与双身份

新不可变信封建议schema aos.eval-subject-envelope/v1，包含可信tenant、taskRun、EvalRun、exact suite/case/规则input与expected refs、exact生成Skill、原generation attempt/AgentRun/requestHash、原query ArtifactRef与query字节hash、原subject ArtifactRef与正文字节hash、stageAttempt、contract、policy、cutoff，以及安装packageHash/generation/epoch/configRef与commandKey。
所有引用从当前受限权威读取；包不自报租户、授权或执行身份。正文/来源完整内容通过受控通道供评测，Receipt仅保存引用和hash，日志不记录文本。canonical规则固定JSON类型、键排序、UTC带时区时间及UTF-8原文字节，不隐式修剪正文。

身份一为独立来源见证者：只证明同一次已成功且有Provider/UsageReceipt的原生成query/text与封套一致，不声称重新执行Skill。
身份二为独立Judge执行者：经当前批准安装调用固定结构评测消息，读取同一封套，签结果与完整封套hash。证书用途、独立公钥、issuer/Owner/approval/有效期/撤销全部显式验证；不能复用target私钥替代独立身份。
结构评测不是内容真实性或人工批准；人审依原职责、权限和exact版本单独完成。

## 4. 一条生产链到消费者

1. 自然生成完成事件触发原协调器；先读取原attempt/产物/query/预算用量/安装fence和Plan gate，失败只封闭本实例，不重发生成。
2. 准备评测意图并持久化稳定key（tenant、stageAttempt、subject、contract、policy、安装代次）；复用Run/事件/Receipt机制。实现前确认原EvalRun创建Owner权限，不能直接SQL补succeeded。
3. 事务内捕获来源封套，事务外IPC评测；回传后在新事务复验所有当前引用和fence。不得跨IPC持有DB锁。
4. 来源见证者和Judge签同一封套hash，Judge输出结构结果hash；签名失败或超时保留意图，未知签发结果按稳定Receipt读取，不重复生成或创建替代Run。
5. 受限writer在SERIALIZABLE事务中核对签名、独立身份、来源、当前性、结果与Run合法终态，原子落Report及证明sidecar；校验失败零写入。
6. 阶段评审消费者从数据库加载证书与Receipt，重验完整封套、撤销、原生成来源及最新Report，再返回原StageEvalReportProof。不得接受页面passed或调用者presented替代持久authority。
7. 仅在上述来源齐备后，让阶段产物评审使用独立的subject-review证明消费路径；保留Skill/Model发布Gate原禁入语义。原Plan/Contract需显式批准subject-review模式，旧合同不自动升级。
8. 原accepted solution decision与获批GrowthPlan→Handoff→Task/Brief为下一组成段；旧OPEN ReviewIssue/四类artifact错位仍须单独修，不能造行或改失败为成功。

## 5. 具体文件范围（批准后才编码）

公共新增候选：services/aos-api/aos_api/aip_eval_subject_proof_contracts.py、aip_eval_subject_proof_authority.py、aip_eval_subject_proof_writer.py；新用途独立于aip_eval_execution_authority.py v1。
领域：services/aos-api/aos_api/ecommerce_analyst_stage_eval_report.py、ecommerce_analyst_stage_review_command.py（原Owner适配）；bundles/solutions/ecommerce-growth/backend/ecommerce_growth/analyst_structure_eval_operation.py仅沿已有接口消费。
生产入口：先复核原AgentRun完成事件与EvalRun Owner，再确定精确接线文件，禁止凭文件名新增第二套运行引擎。
数据库若需独立subject证明表/约束/受限角色，追加当前唯一head后新迁移；不改130及历史迁移，不迁当前真实库。新表名/DDL和Owner权限必须在实现前另附文件级计划，不用本文当任意DDL授权。
测试：新增tests/aip/test_aip_eval_subject_proof.py及test_aip_eval_subject_proof_pg.py，扩展tests/test_ecommerce_analyst_stage_review_command.py真实来源路径；保留旧测试但其monkeypatch通过不计联合正向。

## 6. 验收矩阵与发布顺序

- RED：两份正文/两次generation/两个stage/两个tenant/不同cutoff或安装代次，在相同静态Suite下不可交换证明；签名、撤销、角色、旧epoch、bool/int与时间漂移均拒绝。
- 原签名v1回归及原非阶段Eval行为不变；v1证明不得自动晋升subject-review。
- 真临时PG：独立受限身份、原生成与EvalRun Owner、原writer/reader→原阶段决策；不替换关键校验函数、不手写passed/Report/Run来证明成功。
- 并发/故障：相同key唯一Receipt，writer事务回滚零残留，IPC后撤销失败关闭，签名响应未知只读对账。
- 完整联合必须记录原事件→生产者→签名→Report→accepted决策；通过此门后再实际自然链。测试密钥与fixture只证明代码，不代表客户authority。
- 新签名制品构建/安装、当前DB迁移、正式身份配置与自然Host启用分别走原安全波；真正业务完成仍以原231首链/八场景/持续观察证明。

## 7. 风险、回滚与裁决

风险：新增用途/主体证明是公共合同增量，必须用户评审；现有正式issuer/身份尚未核实，代码完成不等于可启动。回滚只关闭subject-review消费，保留证据和原v1，不删除历史Run/证明。
需要裁决：是否接受独立subject-review证明用途，绑定完整封套且不重执行生成Skill？推荐接受此方向，随后逐文件实现；不接受则保留禁入并重新审查原产品评测语义，不走高权或伪证明捷径。
本波完成判据仅是可复核证据与可审方案，不晋升任何业务GREEN。Goal保持active，其他已授权独立主线可继续。
