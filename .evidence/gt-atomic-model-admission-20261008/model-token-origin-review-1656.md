# 原 token 来源调查复审

2026-10-09 原 retained 正向库只读实际调查完成，两条原批准申请、Model、冻结 Contract canonical hash 相符；原 caller ABORTED，AgentRun/capacity/Eval hold/caseResult 均零。八个内存反例均由原 RegisteredModelRevision 实际拒绝 extra_forbidden：tokenizerRef、tokenizerArtifactHash、messageEnvelopeRef、inputTokenCount 各两次。未写库、未改原合同/审批，旧证据和产品文件 hash 保持。

原合同已冻结 prompt/wire，但没有 token policy；Model provider_model_id仍为隔离fixture的 m，没有正式模型 tokenizer 来源。AST定位原 transport发送在173行，Usage prompt_tokens读取在526行，属于调用后证据；该检查只证明当前精确调用路径顺序，不证明所有模型或Provider行为。实际输入 token 数保持 null，不能误判为0。

结论 TOKEN_AUTHORITY_ORIGIN_MISSING 是明确局部来源缺口，不是完整token gate GREEN。现有注册Model schema不能靠塞额外字段获得可信token来源；任意 capabilities 文本、Contract扩展dict或客户端数字也不具备发行/验证权威。缺口由当前保留DB和typed反例确认，不仅是字符串搜索。

原已登记后续合同细化：需要独立不可变 tokenizer来源/兼容证明绑定精确Provider/model版本和artifact hash，服务端受控parser、完整messages开销和每case wire输入、原审批冻结及currentness。新增产品文件/迁移需先登记精确Task/Lease与完整方案，不能直接改旧Model schema或已发布迁移。下一安全候选继续原Source trusted-end协议（先核Task/Lease），或在原Model evidence范围完善token可信来源发行合同；不调用无授权Provider获取usage。

本轮仅调查辅助代码，符合方案，无产品行为变化；浏览器不适用。Prime独立review原未知attempt不重发，本地复审不冒称独立模型PASS。Main/full Goal仍ACTIVE，无Delivery，不扩大局部缺口为全面停工。
