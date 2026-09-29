# W5CB4 BG-00q｜正式 Skill Eval 执行权威前置禁入方案

## 复习与现状

231 首链要求真实来源、自然执行与可复验产物；228 G2 的内容事实性/渠道适配 Eval 不能来自注入回调。AIP-4 E1B 的精确引用 Runner/Report 是既有保护，但不证明回调的执行主体。BG-00p 核验 `JudgeRevisionRef` 只有 DTO，当前库和代码没有独立 Judge/Target executor 签发、租户、撤销与执行 Receipt 权威；`run_by_contract` 先验 frozen/ready Contract，再把调用方的三个 callback 交给 `run`，后者在 callback 前创建 EvalRun。现有隔离 Skill 发布测试使用 lambda 产生 Report，不能算 D01 真实评测。

## 本波的最小实现范围

1. 本波只在 `services/aos-api/aos_api/aip_eval_runner.py` 的正式 `run_by_contract` 入口加前置判定：从同租户 Registry 读取 Contract 的 exact Suite，先核 Suite revision/hash；若目标是 `SKILL_TEMPLATE`，在独立 Judge/Target 执行权威缺席时，明确拒绝，发生在 `run()` 和任何 EvalRun 创建之前。不得从 caller callback、actor 名称、测试开关或 `JudgeRevisionRef` 自报字段获得放行。LogicGraph/既有 `run()` 语义暂不改变。
2. `services/aos-api/tests/aip/test_aip_eval_runner.py` 加隔离 PostgreSQL RED：同租户 frozen/ready exact Contract 指向 Skill Suite，调用注入 callback 仍必须拒绝；三个 callback 零调用，EvalRun/Report/Gate 计数不增加。另核 Suite hash 漂移也在写前拒绝；既有 Logic exact Contract 正例维持。
3. 不新增迁移、不改当前真实库、`aip_release_publication_service.py`、Registry 和现有 Skill 发布历史测试。此门只封正式 Contract Runner 入口；直接 `run()` 的旧隔离/兼容路径和由其形成的发布门仍是待关闭风险，下一波必须在 E2 `derive_gate/publish` 处核独立执行来源，不能把本波称为全域正式发布安全完成。

## 验证与退出

先跑新增 RED（必须因缺前置门失败），再做上述单点实现；跑 Runner 专项与相邻 Registry/Release/Skill 累计、编译与 `git diff --check`。DB 写测试仅隔离 schema；当前 `aos_current_preview_20260927@a0v_111` 只读。无页面变更，HTTP 健康只做回读，浏览器业务验收不因本波提高等级。最终记录未解的签发 Owner/正向执行权威、legacy `run()`/E2 发布路径和 BG-00o MinIO 网络阻塞；Host/worker/Provider、旧 12 Run、230 L0 保持禁入。
