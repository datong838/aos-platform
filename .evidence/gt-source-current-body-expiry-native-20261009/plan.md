# 当前消费者跨越 Source 原有效期的真实禁入

使用 Rules：用户 AGENTS.md、aos-engineering-delivery、231、原 Source/current Owner 合同。基线 d8cb434e / AOS-001629；上一轮真实 body 过期后 COMMIT 观察已收口，pytest teardown ERROR 保留，不计全绿。

候选①消费者在原 Source 到期后拒绝，依赖原签名 Source、原 SCRAM、正式 fixture 当前 Owner 与完整原事实profile，已登记在1629下一步；候选②distinct最终提交时间观察，依赖独立新库和约五分钟真实窗口，后续继续。选①先 shared。只写本目录 plan.md、task.json、test_current_body_expiry.py、run_native.py、verify_native.py 和精确证据，产品/原fixture/当前权威库/服务不改。

原全迁移 bootstrap 新保留库。使用原 public prepare/sign/finalize 并实际COMMIT，JWT真实签名、有效期覆盖 Source 原窗口，不改 Source/审批/basis 期限。读取另一已有 Owner，签发新的真实消费JWT；新的SCRAM xid/pid与maker不同，Source当前时真实读取成功且executionAllowed=false。回滚读取事务，等待原数据库clock越过Source.valid_until+0.1，最长360秒、每次等待<=1秒。以同一精确SourceRef和仍有效消费JWT，在新的事务分别调用原Python消费者与原生public SQL；固定拒绝、保存真实SQLSTATE/原因，不靠伪身份、DDL替代、缺接口或认证过期制造负门。前后Source hash/signature/provenance不变、occupation六表零、副作用零。

原fixture teardown会再检查已到期签发材料，既有固定拒绝异常并非本体调用失败。仅本目录覆盖原generator的外层清理处理：执行完整原generator，只有清理后精确CAPACITY_NATIVE_SIGNED_SUPPLIER_INPUTS_REQUIRED且独立数据库clock确实越过原Source期限才记录为到期拒绝；其他异常原样抛出。不改产品拒绝语义、不吞业务异常、不改此前失败日志。独立最终核对NOLOGIN、临时接口撤销及原31资源。无浏览器必要；完整Source/epoch/legacy交付、模型review、自然首链继续待验。

r1诊断22.81秒在业务调用之前ImportError，TenantScope实际定义于aos_api.tenant_scope。保存test-r1.py.txt和原r1结果/日志；只读核对该保留库Source未发布及清理后接口撤销。仅改本目录测试导入为正确路径，使用新r2请求和新全迁移库；不复用r1、不把测试失败当产品RED。

r2真实正向消费和原期限等待成立，但319.46秒后负门为SQL42501 CAPACITY_SOURCE_ISSUER_BOUNDARY_DRIFTED，Python前置拒绝未含SQL原因，不算到期通过。诊断等待中rollback清除了SET LOCAL scope/search_path/UTC；原测试每次回滚后调用_refresh_native_facts_transaction。保存r2测试/结果/日志及独立持久化读回，不重发原事务；r3仅在两次负门之前调用该原helper恢复相同连接边界，使用新全迁移保留库、相同完整正向再真实等待原期限。失败不得通过放宽为42501或接受任意拒绝掩盖。

r3连接边界已恢复，正向成立；319.03秒后Python与SQL都由P0002/query returned no rows拒绝，具体具名到期门断言RED。静态定位原CAPACITY_NATIVE_APPROVED_SOURCE_ROW_SQL先过滤过期proposal/current_event，read_original_source_facts随后的SELECT INTO STRICT因此可先抛P0002，早于具名到期检查。不把P0002改成期望结果，不重发原COMMIT。下一步仅独立只读对账原审批期限/Source哈希签名/六表/角色与接口/资源，落盘准确拒绝与原因诊断；Task保持ACTIVE直到原合同的明确拒绝语义和完整场景核查完成。预备finalize_diagnostic.py不得运行；它原要求成功证据，现禁止以此收口。
