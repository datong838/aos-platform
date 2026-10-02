# GW-b-2c2c1b3c2d2b1｜阶段 Task/Brief 来源 markings 保真

基线 `AOS-001123` / `m1 5421f408`。已复习 231 主计划、231-5 §1/§9、栖月汇六同事统一 Task/Handoff 产品方案和 BG00GW D-waves。正式受限 API/Host 身份与八配置仍缺失；本波只修尚未启用的 accepted-stage v3 来源持久化，不打开 Host/Provider。

## 当前缺口

`ReviewAdvanceHostService._review_lineage` 的 accepted-stage `sourceLineage` 保存 16 项，但原 Stage Eval/permission Owner 复验需要命令的 `markings`。Handoff 顶层虽有 markings，Task.goal 与 Brief.spec 未保存，内容生成消费者不能只读 Task/Brief 重建同一组完整来源。v3 目前仅隔离 PG 测试写入、Host execute/Receipt 失败封闭，尚无正式实例 v3 数据。

## 文件级实施

1. 在 `services/aos-api/tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py` 的 v3 测试先增加 `markings` 为第 17 项，并校验 Handoff/Task/Brief 同值；预期 RED。
2. 仅在 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 的 accepted-stage `sourceLineage` 加入 `markings`，旧 Issue 分支、v1/v2 Task/Brief、来源校验和 Host 禁入不变。
3. 跑专项及相邻回归、py_compile、diff-check；复审哈希/幂等、租户与权限边界。文档与 verification 收口后继续 d2b 原 Host Owner/Receipt 合同 RED。

不迁移当前库、不读商城源、不重放旧 Run、不手工 Run、不启 Host/worker/Provider、不 push。
