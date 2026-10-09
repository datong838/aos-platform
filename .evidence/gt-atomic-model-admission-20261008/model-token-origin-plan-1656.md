# 原 Model 调用前 token 权威来源调查

Rules：231、原完整 Model-proof、当前 Task/Lease、m1 单写；真库只读、Provider/Host/worker 关闭。此步为已登记 token 来源调查，不新增产品授权，不变更原 Model 或旧冻结合同。

候选一：Source trusted actual-end 完整协议，依赖 Source 独立 Task/Lease 和实际结束正向证明。候选二：Model 原批准 Target wire 的可信 tokenizer/消息开销，本轮选择后者，依赖精确 Model、Provider revision、原批准 Contract、完整 case wire。已准备 wire 不能证明输入 token 数。

精确文件目录仅 `.evidence/gt-atomic-model-admission-20261008/`，新增本方案、`audit-model-token-origin-1656.py` 和调查结果/复审；产品文件不修改。已有 Owner、Model contracts、transport 只读。当前 Authority AOS-001656、Main ACTIVE，Lease 属于本唯一 owner，有效至 19:36:28 UTC；无异属 ACTIVE Lease。

调查使用上一正向保留库 aos_test_9f7e075e13ca_ti4_test，固定原容器/cluster，SERIALIZABLE READ ONLY。核原请求、Model、Contract canonical hash，caller aborted、四业务表零计数。对内存中的原合法 Model payload 分别加入 tokenizerRef、tokenizerArtifactHash、messageEnvelopeRef、inputTokenCount，要求原 typed contract 实际拒绝，记录精确错误；不向数据库登记、不重跑申请/审批、不发 HTTP。

同时按 AST 核原 invoker 的 transport 发送和 Usage 获取先后顺序，明确后验 Usage 不能替代调用前计数。保存当前文件哈希、HEAD、原证据哈希和 DB 身份。此证据若确认来源缺口，只判 TOKEN_AUTHORITY_ORIGIN_MISSING，不判完整 token 门 GREEN 或业务失败。

下一实现合同必须绑定精确 Provider/model candidate、不可变 tokenizer artifact 与版本/hash、固定 messages 模板/消息开销、允许的输入模态、实际 wire hash及 executor身份；须在原批准前冻结，服务端解析并验证可信来源，完整每 case 实际 token 加输出预留不超过原 Quota/context。不得以调用者声明、字符数、任意模型映射或后验 Usage替代。没有当前可信来源前不写假计数器；先登记所需合同与精确新增产品文件范围，再按原审批/Task 范围实现。

浏览器不适用，直接只读原权威库与纯内存契约反例。验证不新增 DB、行或外部效果；保留旧 evidence，未知结果不重发。Main 不 Delivery，完整 Goal ACTIVE。
