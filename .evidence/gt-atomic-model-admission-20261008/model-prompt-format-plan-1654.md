# Model 原审批输入格式实现

Rules：231、原 Model-proof / Main 全包，先原数据证据与方案再编码；m1 唯一写者、保护现有功能/数据、无 Provider。上一波 RED 明确 frozen 原 Contract没有唯一 Model 提示词转换。本轮完善同一已登记主线，不更改完整退出条件。

候选一为 Source 可信实际结束协议（依赖父终态设计，单 PRECOMMIT 已反例）；候选二为 Model input/format/token/wire 接线（已获隔离设计/实现授权）。选候选二，实现原 frozen Contract 绑定的确定性 prompt producer必要阶段，后续仍需原 Model/Quota token/context与wire/Source终态，不把此门作全包交付。

产品修改精确位于 `services/aos-api/aos_api/aip_model_eval_execution_owner.py` 与 `services/aos-api/tests/aip/test_model_eval_execution_owner_pg.py`，均在现 Main Lease。新增测试 helper、runner、审计/结果仅 `.evidence/gt-atomic-model-admission-20261008/`。不改旧helper、Skill、Budget、Source、迁移、审批机制或当前库。

固定首版policy：gatePolicy.subjectKind=model_eval、executionAllowed严格false，modelInputFormat精确为 schemaVersion=aos.model-eval.single-user-prompt/v1、inputSchemaHash（精确固定 JSON Schema 的 canonical hash）、renderer=aos.model-eval.single-user-prompt/v1。schema只允许 object {prompt:非空string}，required prompt、禁止附加字段。实际renderer额外拒绝全空白和不能编码为UTF8的孤立surrogate；不去除空白、不normalize内容。无任意模板/回调/system/tools/动态codec。canonical policy比较区分bool/number，未知版本/字段一律拒绝。

新 Owner method先复用上波原完整input bytes/Suite/申请/批准/hold同caller当前性门，再经原 ProductionContractStore在同conn读取exact已冻结Contract。schema/policy值只接受本版本。输入hash已原审批，按固定字段读取后产生完整有序 tuple(caseId,原promptUTF8 bytes)；解析/编码后再次复核完整input/原Contract当前性。返回非执行准备数据，不持久化事实，不冒充 Model executor 身份、签名、Usage或准入。实际messages/wire codec尚未绑定，方法名明确prompt bytes，不称 request envelope。

正向不能改旧冻结行或借原caseId案例：新隔离fixture使用原已发布Model、原治理契约建立全新prompt Dataset/Artifact元数据/Suite/冻结Contract，然后原maker申请与独立签名checker审批。保留治理Graph仅作为原控制面readiness，不作Model质量；新prompt输入/schema/hash已经纳入新Suite/Contract和原审批hash。原helper字节副本不变；只在显式 AOS_MODEL_PROMPT_FORMAT_PROBE=1 下用新helper包装原注册入口，正常路径不变。

r1 在新Suite注册前由原typed parser拒绝 VersionedAssetRef-as-AssetRevisionRef，属于fixture前置失败；保留原库/副本/日志，不作producer缺失RED。r2用原已注册旧Suite的精确typed target值，在全新目录和数据库重做独立尝试，不覆写r1或重放其申请。

GREEN r1新prompt方法本身已返回精确bytes，但相邻原证书fixture明确按两case/四证书验证，单case使其中重复集合负门等同合法集合而失败。保留失败，并恢复完整两case：新Model Dataset manifest/source明确两个case，Suite对应两份新input ref，不复制治理case或缩小证书测试。再以全新r2数据库复验。本轮不修改原证书fixture。

RED用一新数据库在原申请整组准备后证明新producer方法不存在。GREEN用新数据库验证新policy+中文/emoji/换行/边界空白原prompt bytes保持精确；另新库负门分别用实际批准的缺字段、多字段、wrong type、空白、escaped surrogate、未知policy。输入Byte hash篡改与漏case交由已存在完整bytes门的相邻测试，不通过改hash跳过。旧未带policy申请必须继续拒绝。

独立只读核保留数据库/原request/Contract/Suite/输入hash/caller实际xid回滚、无AgentRun/capacity/hold/caseResult、旧evidence与原Source verifier不变；检查本method没有SQL写入、网络或事务控制。方案/代码复审后精确提交与AOS/Prime同步，Main/Goal继续active。浏览器不适用本无UI变更。新format不能在正式环境自动注册、自动升级或授执行。
