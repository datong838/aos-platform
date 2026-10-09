# 原完整案例输入字节门自审/验证

Rules：231、原 Main 全包与 Model-proof 合同，m1 单写，无正式执行。新增业务逻辑位于 services/aos-api/aos_api/aip_model_eval_execution_owner.py；原 whole-plan 测试只在显式 probe 参数下覆盖新门，未改旧 Skill、预算内核、迁移或数据库角色。

原 Model 申请/批准/hold/Suite 必要准备之后，现在可以在同 caller 核完整 immutable ordered case/bytes 集合。复用原 Suite/申请全部当前性，解析前后各核一次；每份原生 bytes 非空且最多原 1MiB，UTF8 JSON 严格拒绝重复键、嵌套重复键、NaN/Infinity 和 exponent 解码出的非有限数；SHA256 直接核原登记字节，不把相同 JSON 值/尾空白归一化。不接任意 resolver，不写 SQL，不创建身份/Intent/准入事实，返回 None 不等于实际执行许可。

本轮证据：r1 前置失败源于原 pack 正确拒绝 Model-as-LogicGraph；已按原同 dataset registry 读取 LogicGraph ref 修正。r2 RED 明确缺新消费方法。GREEN r1 原两 case 与十二负门通过；复审新增错误来源匹配/嵌套重复/exponent overflow，r3 RED 正确暴露普通 parse_constant 漏洞；最小 parse_float 有限检查后 GREEN r2 1 passed/7 warnings/10.10s，十四负门全部通过。相邻原 evidence 隔离五项测试通过。没有覆写或重跑任何旧尝试。

独立原生只读五个保留数据库：每次均有两份原登记批准申请，实际 caller xid 全部 aborted；AgentRun、Model capacity、Model Eval hold 和 Model case-result 均零。两次 GREEN 的原 Suite canonical hash/案例 input hash 与本次字节摘要逐项一致；两份旧 legal evidence hash 和原 Source C verifier 不变，容器未重启。该模型案例仍是内容治理 subject 的 28-byte 测试输入，明确不能当真实 Model prompt、质量或 tokenizer 数据。

方案/代码一致性：严格字节而非重序列化值；case 必须完整且有序；原 native caller/租户/申请/批准/原 Suite 桥沿旧 Reader，无复制权限算法。新增门没有事务控制、网络、dispatch/admit 或直接 SQL。既有默认测试路径和原治理接口保留；完整 Main Task 未 Delivery。

限制和下一步：本门不证明 Artifact 存储读取渠道、Model-specific schema/rendering、当前精确 tokenizer、输入加输出的 context 硬界、真实 HTTP byte hash 或独立 Judge 原 Target 输出。继续沿原 Model-input-envelope-next-plan，先建立有原权威来源的输入 producer/formatting，再在完整 Source/预算/唯一 Intent/实际终态协议后接 transport。不能把 DTO、输入门、注册为 ready 或本次测试代替全链质量和正式首链。Prime 独立模型审阅仍保留此前 daemon 归属失败限制，本次不声称独立模型 PASS。
