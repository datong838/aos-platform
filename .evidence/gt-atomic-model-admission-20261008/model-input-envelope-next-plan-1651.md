# 下一产品子波：真实输入与 Model/Quota 硬界

Rules：231、原 atomic Task 全包、单一 m1；先方案与原实际 transport 数据契约，再 RED/最小实现。不得将新的 DTO 或 hash 检查当联合准入、实际 tokenizer 或质量通过。

候选一可信结束协议：本轮原生 callback 后置等待反例已交付 AOS-001651，严格实际完成门仍需完整协议，不能扩大 TTL 或静默缩小。候选二完整 Model/input/风险接线：沿已登记 whole-plan-allocation-findings 与 joint-risk-active-protocol，先处理实际输入边界。选候选二，先调查原输入/transport Owner，再写代码。

拟修改范围仅现 atomic Lease 中 services/aos-api/aos_api/aip_model_eval_execution_owner.py、aip_physical_capacity_occupation.py/contracts.py、tests/aip/test_model_eval_execution_owner_pg.py（准确依赖核完后收窄）。目前不改这些文件。明确原 RegisteredModel contextWindow8000 与 Quota8000输入/2000输出各自语义，10000 是保守 physical token 占用，不等于10000合法上下文。既有费用未定价继续保留风险。

调查文件为本目录 model-input-transport-investigation-1651.py/json/md：AST 与 exact hash 绑定现有 ExactProviderInvoker、原 LLMAdapter、Model owner、原 EvalRunner Artifact hash算法及 typed signing input；只调用无网络解析/编码原函数或只读目录，禁止调用 invoker.__call__/transport/Provider。确定 Artifact JSON canonical hash 与实际请求 UTF8 bytes hash、max-output 参数及模型上下文/Quota如何真正传递，避免复制旧 Skill caller 任意 resolver 或补一个描述性 cap 函数便称已实现。

下一 RED 必须覆盖完整实际请求字节、模型/Quota exact refs、输出预留及超硬界不 dispatch；若原 transport 本身属于旧 Skill，新增 Model 专用 producer/transport 文件先精确登记范围，不改旧 Skill 签名域、预算、已发布迁移或直接删除 Runner 否认。新的可信 Subject/Root、Source实际COMMIT、unique Intent、Usage结算仍按原全包继续，Task 不收口。
