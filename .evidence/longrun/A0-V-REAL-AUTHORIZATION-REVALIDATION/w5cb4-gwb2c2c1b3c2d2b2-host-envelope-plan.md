# GW-b-2c2c1b3c2d2b2｜宿主生成 v3 来源命令入口计划

基线 `AOS-001125` / `m1 3789b753`。复习 231 主计划、231-5 §1/§9、栖月汇统一 Task/Handoff 产品方案与 BG00GW 清单。Task/Brief v3 已记录 17 项来源；包内新生成命令已有 `sourceKind=accepted-stage-v1` 和单原 `Artifact`，执行函数仍在调用 port 前关闭。宿主 `_strict_content_generate_command` 目前仅支持旧四 `ArtifactRevision`，且 Host execute 有预算保留逻辑，不能单靠放宽 parser 就开放新分支。

## 当前切片 d2b2：严格宿主命令与三入口零副作用禁入

- `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py`：先 RED 新命令精确字段、单原 Artifact、hash、来源混淆和 returnDecision 混用的拒绝；同时验证 Host revalidate/execute/verify_receipt 在读 DB/保留预算前封闭。
- `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：严格解析新分支并返回显式 `sourceKind`；旧分支字段、四引用与回执哈希不变。Host 三入口对新分支明确失败关闭，防调用者绕过包内前置门而触及预算/Provider。
- 专项/相邻回归、py_compile、差异检查；复审旧 Issue 路径与新命令含分支种类哈希。浏览器读回禁入；verification 与 m1 精确提交、D-waves/AOS/Prime 同步。

本切片只把合法新命令送到明确禁入门，不是原 Owner/Receipt 消费。下一切片 d2b3 必须从当前原 StageDecision/TaskRun/Plan/Attempt/Eval/Artifact/permission/GrowthPlan 和 Task/Brief v3 同事务回读，再接可读 Artifact 与人工评审；全部齐备前不得解除三入口门。当前正式 OIDC、八配置、Host assignment/binding、Growth1.13 仍独立缺口。真实库只读、无商城源/旧Run/手工Run/dev-org写/Host/Provider/push。
