# 原 Target 实际请求字节准备接线

Rules：231、Main完整Model-proof退出条件、m1唯一写者、无Provider/正式库效果。产品精确修改仅services/aos-api/aos_api/aip_model_eval_execution_owner.py及tests/aip/test_model_eval_execution_owner_pg.py，辅助fixture/runner/验证仅本Main evidence目录，均现Lease scope内。

复习原ModelRuntimeStore：target是当前draft/validated source的下一ACTIVE candidate，原Store在申请/审批/hold当前性流程重算candidate hash并核Head CAS；下一target尚未发布，不能假称已经存在可READY的Model revision。用原source payload构造候选的同一provider model id，仅为approved candidate的非执行准备，不发请求或放开旧Resolver。

已登记候选一Source严格终态协议依赖可信actual-end；候选二Model完整input/format/token/wire，当前完成prompt必要阶段，继续候选二。完整Goal、Main未缩小。输出max_tokens只能从原当前Quota读取，context8000/Quota输入8000+输出2000不是合法10000上下文。预留输入窗口min(Quota输入,context-output)只是硬限容量，不证明实际token小于该值。

新增prepare_original_model_target_wire_bytes：原完整prompt准备→原frozen Contract新modelTargetWireFormat严格版本/codec/role/outputLimitField→同caller读取精确Model/Quota并canonical核Hash/租户/refs→仅TEXT输入输出分支→显式Quota输出cap，要求context-output>0→固定一个user message/不可附加model参数→当前HTTPX实际编码UTF8bytes→复核原prompt/申请/Model当前性。仅返回完整有序tuple(caseId,wire bytes)，不传客户端URL/header/secret/transport，不返回或持久化执行grant、可信token数量或Identity。新格式必须在新Contract冻结并纳入原独立批准，不能改旧冻结Contract；缺格式拒绝。

wire policy精确为schemaVersion=aos.model-eval.chat-json-target/v1、codec=httpx-json-v1、role=user、outputLimitField=max_tokens；额外字段/未知版本/任意role或codec均拒绝。只Target，因为独立Judge必须消费exact Target output和自己的合同，不能复用Target prompt。

补充context负门：新的隔离fixture在原publish_model入口注册全新contextWindow=2000的source，按原Store canonical算法重算hash、形成真实新candidate/申请/独立批准；Quota输出仍2000。绝不UPDATE旧immutable revision或放宽源验证。测试仅在新显式variant下选用此新source，并要求producer实际拒绝无输入空间。保留正向r1的原测试文件快照以复核attempt旧hash；此修改只增加精确negative错误匹配，不改变产品正向路径。

RED为新原注册/冻结/独立批准后缺方法。GREEN核两个cases、原Model provider id、固定角色、输出cap、Unicode/空白保持与实际HTTPX原始字节；negative另fresh审批缺wire policy/错role/错version/额外system字段均拒绝。沿原fullplan回滚/checker/证书/错caller与租户相邻；旧prompt/byte链保留原语义。

独立SERIAL READ ONLY核保留库、原申请/Contract/Suite/Model/Quota canonicalhash、caller实际aborted、全部业务计数0、旧证据/Source verifier不变。严格区分wire preparation和可执行请求：tokenizer、实际Token+上下文、Provider格式兼容、真实Usage、Source结束协议、唯一Intent、executor身份、Judge输出、Report/Gate/正式质量仍pending。浏览器不适用。本轮不发Main Delivery。
