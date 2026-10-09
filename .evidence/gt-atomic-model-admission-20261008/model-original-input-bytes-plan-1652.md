# 原 Model Suite 完整输入字节门（编码前）

Rules：231、model-proof-implementation-contract、原 Main 全 Task/精确 Lease、m1 单写；完整 Task 不以本准备门替代实际联合 COMMIT/Target/Judge/Usage/Report/Gate。

已核原原生 fixture：Model Suite 来自已登记内容治理 pack 的独立 subject 案例，输入是 canonical JSON `{caseId: content-subject}`，Artifact 元数据只有 test-only URI。它不是完整聊天 prompt、Model 质量数据或 tokenizer 证明。当前 validate_original_model_plan_suite 只核原案例/hash集合；尚未核调用者交付的原字节，不能让后继通过任意 resolver 或重新 stringify 值替代字节。

已登记候选一为全 Model 输入/实际 transport/token/输出限制；候选二为完整原 byte 集合必要消费。选候选一主线中的候选二依赖，真实实现而非仅 DTO：在原 ModelEvalExecutionOwner 增加 validate_original_model_plan_input_bytes，同原 native caller 复用原 Suite/原审批/head/parent 全 currentness，收一份 immutable ordered tuple(caseId, bytes)，全部原 case 恰好一次、顺序匹配原 manifest；每份 bytes 原生类型/非空/最多原 Source 输入门既定 1MiB，SHA256 精确匹配签名计划与原 Suite 案例。严格 UTF8 JSON，不接受重复 key/NaN/Infinity 或隐式修正。完整解析后再复核同 caller 原 Suite/申请，失败不写新表，不创建 hold/Intent，不授执行。

精确修改 services/aos-api/aos_api/aip_model_eval_execution_owner.py；services/aos-api/tests/aip/test_model_eval_execution_owner_pg.py 仅在显式 AOS_MODEL_INPUT_BYTES_PROBE 下追加原 whole-plan rollback 节点检查。使用原已登记 pack 原编码规则构造测试字节并先与原表 input hash 一致，不借旧审批；新隔离 root/新数据库分别 RED 与 GREEN。正向完整两 case，负门错字节/缺失/多余/重复/顺序错/可变列表/字符串/超 1MiB，错误 caller；全程 Source/physical/dispatch remain pending。与现有五项 evidence 边界测试和原 whole-plan 相邻累计，独立原表/xid aborted/无输入门新 SQL/零 case-result 回读。

返回 None 仅表示原字节必要门成立；不产出可信签名/持久 receipt、wire payload 或 token 值。后继仍要注册真正的 Model 输入 schema/producer/formatting 与 tokenizer，并将实际 HTTP body hash、独立 Judge Target output、原 Source/Intent/终态一体接线。原 Graph/Skill 入口不改，原 signed 案例 bytes不自动归一化。

首次 RED r1 在输入 fixture 前置失败：原 pack 构造器正确拒绝将 Model target 当 LogicGraph pack 来源，尚未走到缺新接口断言。这不是新接口 RED，不覆写该已知失败。改用同 caller 从原 registry 精确相同 dataset_ref 的原 LogicGraph Suite 读取 target_ref，再调用原构造器；不伪造 graph ref，也不称该内容 subject 数据为 Model prompt。新 r2 另独立数据库和 evidence 根，原 r1 caller 效果只读对账、禁止重发。

第一 GREEN 完整两 case 和十二负集合通过。复审补强 JSON 负门：要求报错确实来自严格解析而非随后 hash 不等，加入嵌套 duplicate key 与 `1e9999` 解码溢出；原 decoder 仅 parse_constant 不足以拒绝 exponent 转出的非有限浮点，先新 r3 RED，再最小 parse_float 有限校验并新 GREEN。每次另新数据库/attempt，不覆写或重放已有父申请。
