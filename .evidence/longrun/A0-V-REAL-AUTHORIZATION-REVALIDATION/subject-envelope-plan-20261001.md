# Subject-review 第一实现波：完整信封

用户于2026-10-01明确“确认并授权按照建议去做”：subject-review与Model评测用途的设计/代码/隔离验证已批准。旧GW-b/GT文档的待裁决为历史状态，不得再作为阻塞。真实库写入/迁移、Secret、Provider、Host不在本次执行授权内。
Rules：AOS AGENTS、aos-engineering-delivery；m1单写无push。依据GW-b §3完整信封及231的来源/预算/批准边界，第一波只冻结原来源的待签名对象，不声称签名/Owner/消费已完成。

## 文件级实现
- 新aos_api/aip_eval_subject_proof_contracts.py：复用原Tenant/Asset/Artifact/Stage/Contract/Policy refs；定义subject-review独立用途信封，绑定Task/Eval/Case/Judge、原生成Skill/Attempt/AgentRun/requestHash、原query/subject字节hash、阶段合同策略cutoff、安装包/代次/epoch/configRef/commandKey。明确结构结果不产生运行READY或发布许可。
- 新tests/aip/test_aip_eval_subject_proof.py：RED先覆盖各来源字段改变会改变hash；异租户/正文/安装代次不能串用；缺字段/额外字段/bool假整数/naive cutoff/错suite或skill拒绝；同一UTC时刻与JSON键顺序一致；原文字节不trim；model_copy绕过校验后再次canonical必须拒绝。
- 签名域隔离AOS-EVAL-SUBJECT-ENVELOPE-v1，SHA256计算原canonical bytes。只接收引用/hash，正文不入信封；源读取与双签名将在下一波接原Owner/签名设施，当前对象绝不是authority。
- 独立Model评测用途授权已确认，仍串行在其文件级计划后开发。不引入skip_eval或伪READY。

## 严格Goal阻塞规则
单实例/单项待裁决不阻断整体。必须整体无可推进工作、安全替代逐项排除、同一根本阻塞至少连续三轮且确需用户实质决策或外部变化，才满足blocked必要条件。断联/超时/RED/无提交不能单独触发。报告替代路径、证据和解除条件；授权后旧理由失效。不得伪造Goal active。

## 验证/交付
专项与原v1签名、阶段Review相邻测试；不触真实库，不加迁移/服务/路由。哈希测试是协议证明，不是签名权威或自然首链。完成后verification、精确提交、AOS/Prime/D-wave同步，随后双身份签名及原消费者接线。
