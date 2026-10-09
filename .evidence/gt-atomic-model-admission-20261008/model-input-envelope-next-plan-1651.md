# 下一产品子波：真实输入与 Model/Quota 硬界

Rules：231、原 atomic Task 全包、单一 m1；先方案与原实际 transport 数据契约，再 RED/最小实现。不得将新的 DTO 或 hash 检查当联合准入、实际 tokenizer 或质量通过。

候选一可信结束协议：本轮原生 callback 后置等待反例已交付 AOS-001651，严格实际完成门仍需完整协议，不能扩大 TTL 或静默缩小。候选二完整 Model/input/风险接线：沿已登记 whole-plan-allocation-findings 与 joint-risk-active-protocol，先处理实际输入边界。选候选二，先调查原输入/transport Owner，再写代码。

拟修改范围仅现 atomic Lease 中 services/aos-api/aos_api/aip_model_eval_execution_owner.py、aip_physical_capacity_occupation.py/contracts.py、tests/aip/test_model_eval_execution_owner_pg.py（准确依赖核完后收窄）。目前不改这些文件。明确原 RegisteredModel contextWindow8000 与 Quota8000输入/2000输出各自语义，10000 是保守 physical token 占用，不等于10000合法上下文。既有费用未定价继续保留风险。

调查文件为本目录 model-input-transport-investigation-1651.py/json/md：AST 与 exact hash 绑定现有 ExactProviderInvoker、原 LLMAdapter、Model owner、原 EvalRunner Artifact hash算法及 typed signing input；只调用无网络解析/编码原函数或只读目录，禁止调用 invoker.__call__/transport/Provider。确定 Artifact JSON canonical hash 与实际请求 UTF8 bytes hash、max-output 参数及模型上下文/Quota如何真正传递，避免复制旧 Skill caller 任意 resolver 或补一个描述性 cap 函数便称已实现。

下一 RED 必须覆盖完整实际请求字节、模型/Quota exact refs、输出预留及超硬界不 dispatch；若原 transport 本身属于旧 Skill，新增 Model 专用 producer/transport 文件先精确登记范围，不改旧 Skill 签名域、预算、已发布迁移或直接删除 Runner 否认。新的可信 Subject/Root、Source实际COMMIT、unique Intent、Usage结算仍按原全包继续，Task 不收口。

## 原生回读接续 r3（编码前）

r1 的临时 passfile 消失，但精确原隔离容器仍运行，启动配置中已有同一 aos_app 角色凭据。本轮仅在进程内复用现有配置：绑定原容器 ID、原 cluster、原数据库/head，显式 SERIALIZABLE READ ONLY；不输出、持久化、轮换密码，不新建角色或改变认证，不重启容器。单独新脚本/新结果 r3 保留 r1 失败，禁止覆写旧证据。原申请仅历史事实调查，过期审批绝不回放；复核原 Model/Quota payload/hash 与实际纯编码。查询失败仅登记本次已知只读失败，不自动重发。

## 新鲜原申请 fixture 的不覆写门（编码前）

r3 已完成两个历史原申请的实际只读 Model/Quota 回读，准备金额/Intent/case-result 数量保持不变。继续输入实现前需要新鲜原申请，不能复用过期授权。现 test_model_eval_execution_owner_pg.py 两处固定 evidence 根会覆写旧 legal-model-prefix/application 文件，直接重跑不合法。

精确修改 services/aos-api/tests/aip/test_model_eval_execution_owner_pg.py：增加显式 AOS_MODEL_OWNER_FIXTURE_EVIDENCE_ROOT，仅接受原 Main evidence 下新的独立子目录；要求两个 helper 字节与原登记 helper 精确一致，拒绝已含旧输出的目录，不自动覆盖、删除或复制旧结果。默认路径的原测试语义保持不变。本 Evidence 新增纯边界测试先 RED，再最小实现；随后仅一次原 Owner 原生节点，用独立目录内精确 helper 副本及新数据库。新 attempt 在开始前绑定 HEAD/文件 hash/原容器，保留数据库与旧文件 hash；只为后续完整输入接线提供新鲜基线，不作 Model 质量或完整准入验收。无生产文件、旧 Skill、迁移或正式环境变更。

### 已知失败后的 r2 新隔离尝试

5434 原生节点在 setup 迁移至 aip1_001 时遇 DiskFull，主体未执行；保留 aos_test_910262635381_ti4_test 和原 attempt/result，不重跑此数据库。不删除 Colima 库卷、不修改磁盘配置。切到已登记 Desktop 外置盘上的 5441 原 Source 隔离容器（精确原 ID/cluster/volume/library），先核可用容量至少 2.5GB、现有 pgpass 权限及卷 Options；另建唯一新数据库、另一个新证据目录/r2 attempt，仍只运行原 Owner 一节点。容量不足即停止该动作而继续其他安全工作。

r2 已真实通过第一 Owner 节点。相邻只选原 whole-plan rollback 节点，另独立 r3 目录和新数据库；whole 模式额外强制验证原 original_plan_certificate_fixture_r1.py 字节一致，不能漏掉执行前证书整组原生接线。相关 Model 业务代码不变。不复用 r2 原申请，不运行等待分支扩大检验范围。
