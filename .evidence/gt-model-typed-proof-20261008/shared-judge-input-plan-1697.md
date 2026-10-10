# 共享父风险v3 Judge输入完整字节协议

Rules：231、joint实施§3/§11.3、Task2精确Lease、先方案后代码、最小更改。产品文件 services/aos-api/aos_api/aip_model_eval_execution_contracts.py；测试与证据 .evidence/gt-model-typed-proof-20261008/shared-judge-input-*。不改原v1/v2/已有v3签名函数，不改DB/guard/迁移/真实效果。

原合同单次COMMIT为准入/预算/物理风险/Intent，并未要求实际Target/Judge结果同次COMMIT。候选A对结果后继阶段的解释与原§3一致，但prepared_only七个原门仍无条件拒绝，不据此实施或授予准入。原v3 case crypto仅核raw inputHash，不推导Judge实际应消费的输入；本轮补充完整确定性字节构造与exact消费者，避免签名合法却Judge读取任意字节。

新增build_shared_parent_target_judge_input：复用原v3 Target证书/签名验证，要求Target用途；绑定全description/manifest/risk/caller、judgeRequestHash、case/dataset hash/JudgeLeg、全signed Target canonical hash、Target证书hash、原始actualBase64、期望hash与字节。期望缺失必须None，存在须exact bytes≤1MiB且hash相符。序列化后长度≤1MiB，与现有签名wire上界一致；返回executionAllowed=false。
新增validate_shared_parent_target_judge_input：先重建上述输入并验证Target来源必要crypto，再要求exact bytes/上界/字节相等；不允许等价JSON重排、额外字段、删字段、换case或实际输出。

真实Ed25519 over明确synthetic事实；现有native描述仅作为形状样本，新的expected/case hash在签发前一并重建，test-only非真实artifact/current来源。测试present/absent/空期望、超大编码拒绝、actual空白/非ASCII字节保持、错证书/签名/Target输出/输入/期限/撤回/case及重排/加字段。RED接口缺失，最小实现，原361相邻保持；DB连接拒绝+actual0，无Provider。复核所有原AST未变和sourcehash。后继完整native reader必须调用exact消费者，并另核独立COMMITTED结果origin/可信Root/current头/准入/真实Usage；本轮纯协议不能代替它。
