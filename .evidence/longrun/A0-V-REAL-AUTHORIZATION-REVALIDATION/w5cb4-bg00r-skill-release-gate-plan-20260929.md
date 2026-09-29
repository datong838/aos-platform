# W5CB4 BG-00r｜未证明执行来源的 Skill E2 发布门禁入方案

## 上位方案与现状

231 首链、228 G2 与 AIP-4 E1B/E2 都要求评测结果可复验，发布门不能消费自报成功。BG-00q 已在正式 `run_by_contract` 阻断缺执行权威的 Skill Eval，但旧 `AipEvalRunner.run()` 仍能用调用方注入的 callback 写 Skill Report；`AipReleasePublicationService.derive_gate` 只核 Run/Report/Suite refs，可能给该 Report 生成 PASSED Gate，`publish` 可再生成 PublicationEvent。当前没有 Judge/Target executor 身份、签名、撤销和执行 Receipt 权威，也没有正式 G2 对象；不能引入测试开关放行。

## 本波文件与最小安全行为

1. `services/aos-api/aos_api/aip_release_publication_service.py`：在 E2 `derive_gate` 完成同租户 Report/Run/Suite 精确读回后、写 Gate 前，对 `SKILL_TEMPLATE` 失败封闭；在 `publish` 验证既有 Gate 的 Report 时同样拒绝 Skill，以覆盖旧 Gate 被再次用于新 PublicationEvent。LogicGraph 既有同事务门控、撤销与幂等语义保持；已存在的历史 Event 只读/相同 key 回放不删除、不改写。
2. `services/aos-api/tests/aip/test_aip_skill_publication_service.py`：现有 `published_skill_runtime` 用测试 `test-only://` Artifact 和 lambda Judge/Target；不得再命名为真实 Eval 正向业务证明。保留其构造到 Report 的隔离能力，新增 RED 证明由它派生 PASSED Gate 目前会成功、但应拒绝；原整链正向测试保留为严格 `xfail`，明确待正式 signer/Receipt 生产链成立才恢复，意外通过必须失败。另以隔离库精确构造历史 PASSED Gate，证明新 `publish` 也拒绝，不借此证明历史 Gate 正当。
3. `services/aos-api/tests/aip/test_aip_release_publication_service.py` 的 LogicGraph 正向与撤销、租户、幂等测试必须继续通过。当前库只读，不新增迁移或制品签发。BG-00r 是禁入门，**没有**正式 Skill Eval 正向路径；下一波先定义并实现真正独立执行权威/Receipt，再按有界迁移与克隆流程开放正向。

先跑新增 RED，再最小实现，跑 E2/Skill/Runner/Registry 相邻累计、编译、差异检查；API 按最新 m1 代码重载并核签名预检和健康。D01、Host/worker/Provider 与自然首链仍不得启动；不读商城源、不重放旧 12 Run、不动 230 L0、不 push。
