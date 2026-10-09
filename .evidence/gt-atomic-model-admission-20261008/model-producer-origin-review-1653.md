# 原 Model producer 来源调查复审

原 AOS-001653 / m1 603eb3b12。当前 Main Lease 同 owner 且有效，全 scope 无重叠 Lease。使用前轮 GREEN r2 保留库 aos_test_841069306b60_ti4_test / cluster7694680278363095064，没有重跑申请、审批或测试，不读正式库。

实际读取两份原审批申请、frozen Contract、原 Suite 和原 RegisteredModel/Quota；分别复核原 canonical hash。原 Contract gatePolicy 精确为 subjectKind=model_eval、executionAllowed=false，没有 Model input renderer policy。原案例 pack 28byte 输入与 frozen Suite hash 相同。用现有 assembler 加当前 HTTPX 实际编码：完整 JSON 与 caseId 字符串产生不同 wire SHA；两种转换均未获原 Contract 授权。本轮没有选定其中一种作为执行实现。

结果 RED_ORIGINAL_MODEL_INPUT_PRODUCER_NOT_FROZEN：上轮输入 byte hash 已通过仍不足以导出唯一批准的 Model 请求，必须补 Model 专用输入格式的审批来源。该 RED 来自原申请与 frozen 原文加实际纯编码；脚本 exit0 表示调查成功，不表示产品正向测试或 Model 准入通过。固定 fixture policy 的缺失不能被推广成全系统所有 Model Contract 都缺失；下一实现范围是本 Main 的原 Model 专用输入路径。

初次脚本因引用错误模块在连接前失败；纠正到原测试使用的 ecommerce_content_pre_review_pack。第二次只读核对因错误地将 metadata 纳入 Model canonical hash 失败，连接上下文已退出并回滚；改为原 Store 的 _META_FIELDS 和原 Quota hash算法后成功。没有数据库写入或未知外部结果；这两次是调查实现错误，不能当产品 RED。当前最终脚本及此说明保留错误原因，不冒充原生业务缺陷。

审查：两父申请的 input hash相同但 actual model 和 quota refs独立读取；输出 cap显式从每父Quota取得，仍不是输入token/context验证。四个业务计数前后均零，只有 readonly SELECT 和 transaction setup/rollback，没有 secret resolver、transport、审批、hold 或写入。模型/输入原文没有打印；结果只存精确refs/hash与有限参数。未改生产代码，故无新增产品逻辑自测；本次原生调查完整通过。没有浏览器变化，本门不适用浏览器验收。

下一产品实现方案（非注册或授权事实）：在原 frozen EvalContract gatePolicy 中建立版本化 modelInputFormat，冻结 formatVersion、input schema、renderer identity/hash、wire codec与 tokenizer identity/policy。建议首版 exact UTF8 JSON {prompt: nonempty string} →单 user message；只允许固定字段/角色，不接受调用者函数、附加 system/tool messages、任意模型参数或 token声明。原 Suite各case输入必须依据新格式重新登记并经新原申请审批；旧已冻结 Contract 不能原地变更，旧 caseId治理输入不得自动升级。Judge输入另冻结 exact Target output/expected引用和自己的 producer，不能暗用Target申请。

具体实现仍在已登记 Model Owner 文件内读取原 frozen Contract，随后新增 Model 专用 producer精确文件先扩 Scope/Lease；按原请求同 caller/当前性/整组input约束执行。真实tokenizer治理来源缺失保持局部拒绝，继续联合Source实际终态与其它安全主线。新格式 reader/renderer正向必须来自独立新原生Contract/申请，不能把此历史fixture改成READY。主Task/Goal未完成。
