# 原批准固定 prompt producer 阶段复审

Rules：231、原 Model-proof 全包、m1 单写。精确产品修改是 aip_model_eval_execution_owner.py 新方法 prepare_original_model_plan_prompt_bytes；test_model_eval_execution_owner_pg.py 新显式隔离 probe /测试。既有默认流程、旧 Skill、预算/Source/迁移/正式库没有修改。本 Main 不发完整Delivery。

实现与方案：先消费原已批准完整有序 byte集，锁和复核所有原申请/批准/父hold/Suite/current Contract；同conn复用 ProductionContractStore读取exact frozen格式；只接受原 model_eval、严格executionAllowed=false及首版精确格式/schema hash/renderer。canonical比较拒绝未知/附加policy字段，既有无格式Contract不自动升级。JSON严格性/hash由已完成原bytes门负责。仅 {prompt: native非空白string}，孤立surrogate拒绝，UTF8输出保留中文/emoji/换行与首尾空白。完整tuple返回不持久化、不签发，不授Model executor/准入；实际消息角色/HTTP codec仍待接线。

新fixture有自己的prompt Source/Receipt元数据、Dataset、输入refs、两case Suite与新frozen Contract，经原maker申请和独立签名checker批准；不是修改旧冻结行。源清单caseCount=2对应两case，case原文字节经新Suite hash固定。原控制面readiness仍用原治理Graph发布；artifactSchemaRef仍是原治理产物schema，不能当Model输出schema、Model质量或正式Dataset脱敏认证。输入值只在隔离helper中存在，没有实现正式Artifact读取渠道。

验证过程：RED r1为fixture target类型前置失败，已保留。RED r2在两份新原批准申请/整组Suite准备后明确报producer方法缺失。GREEN r1新方法正向成功，但单case破坏原四证书fixture的重复集合负门；保留完整失败。修正新Dataset/Suite为两case、原证书fixture不改后GREEN r2完整1 passed/7 warnings/9.43s。十二次不同新库分别实际批准 extra、missing、number、empty、whitespace、surrogate、version、no-policy、top-level、schema、renderer、extra-policy输入/契约；均1 passed，全部在新方法拒绝，仍执行原checker撤回恢复/证书/错caller/错租户/原回滚相邻段。无旧申请重放或未知效果重发。

相邻：新原内容输入whole rollback节点仍1 passed/7 warnings/9.36s，包括原字节十四负门；新fixture隔离纯门5 passed/0.66s。新逻辑AST无直接execute/事务控制/网络/dispatch/admit，唯一控制面读取经原Store且显式同conn；parse前后复核。当前 frozen Contract数据库行是原append-only控制面，不接调用者传入policy对象或任意renderer函数。

独立原生SERIAL READ ONLY回读17保留库：两已知前置/相邻失败与缺方法RED均保留，不混同GREEN；有caller记录的所有xid确实aborted，原request canonical hash、frozen Contract完整CreateEvalContractRequest canonical hash、原Suite hash和精确input SHA逐项一致。正向prompt SHA/长度直接核独立预期UTF8字节，两case完整。AgentRun/Model capacity/Model Eval hold/caseResult全部0；全部attempt精确文件hash、旧legal证据和Source C verifier不变，容器未重启。结果 ORIGINAL_APPROVED_FIXED_PROMPT_PRODUCER_NECESSARY_STAGE_VERIFIED 不是完整准入PASS。

风险/限制：固定v1 renderer只生成prompt bytes，未认证动态多角色输入、模型质量、正式producer/Artifact渠道、Target/Judge身份、独立Judge原Target输出、tokenizer上下文、实际wire/输出硬界、Source实际完成、唯一Intent、Usage/Report/Gate/发布。inputSchema固定literal及renderer版本必须保持冻结语义，后续变化使用新版本和新批准Contract。Prime独立模型review仍保留既有daemon归属失败，本轮本地方案/代码复审和原生独立回读不冒充模型review PASS。无UI变化，浏览器不适用。本Task/Goal继续active。

下一已登记步：在此原格式准备之上，核原 Model与Quota exact source/candidate和上下文上限，建立固定单user消息的实际wire codec与显式输出cap绑定；需要可信tokenizer来源和原Target/Judge独立授权，不能把prompt byte长度或caller token声明代替tokens。任何transport必须在完整Source/physical/parent/唯一Intent实际COMMIT已知后，保持当前拒绝门。
