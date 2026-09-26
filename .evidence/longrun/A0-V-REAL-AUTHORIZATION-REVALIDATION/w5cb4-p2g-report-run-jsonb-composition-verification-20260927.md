# W5CB4 P2g 第 4 段子证明｜真实 Report/Run JSONB 与候选读取兼容

- 在 `test_aip_ecommerce_content_eval_input.py` 的一次性完整迁移库中，公共 AIP Task/Plan/Run、`content_generate` 四相 TAOR/StepRun succeeded、可读 `ecommerce_content` Artifact 与 `AipEvalRunner` 正式主体报告均持久化；新增断言让内部候选读取器实际查询同库报告、EvalRun 和原批准 Plan gate，得到同一 Artifact/StepRun/Report 身份。
- 为隔离本段目的，仍对**预算结算/Provider+Usage Receipt 来源、当前 dispatch、生成 checkpoint 完整 payload、正式当前 EvalContract 来源**使用注入接缝；因此这不是“同一 reservation 到待办”的正向验收，不授权 GET、Issue 创建或生产激活。此前 `test_a0v_content_result_consumer_pg.py` 的 Receipt/Artifact 测试位于另一个精简 schema 且需 opt-in，不能与本段绿色相加冒充同库闭环。
- 新增断言后的单例完整迁移库测试 `1 passed`；内容＋通用 EvalRunner 累计 `283 passed, 9 skipped, 7 warnings`；`git diff --check` 通过。纯后端，无浏览器改动。当前实例仍 `a0v_092` 且内容预审包未安装。
- 下一步：在一次性完整迁移库构造正式 settled 内容结果和两类 Usage Receipt，与已有 Task/Plan/Artifact/StepRun/报告统一同一 ID；去掉上述接缝后再跑完整 RED/正反。若正式 API fixture 无法在该库构造，逐项记录缺失权威并补最小可复用 fixture，不放宽读取器。后续再接 ReviewIssue/人工决定。
