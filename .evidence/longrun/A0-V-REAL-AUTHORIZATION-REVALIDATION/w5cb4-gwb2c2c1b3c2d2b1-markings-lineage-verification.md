# GW-b-2c2c1b3c2d2b1 verification

基线 `AOS-001123` / `m1 5421f408`；Task `W5CB4-GWB2C2C1B3C2D2B1-20261002`。方案：`w5cb4-gwb2c2c1b3c2d2b1-markings-lineage-plan.md`。

- RED：在 v3 Task/Brief 隔离 PG 测试的 exact `sourceLineage` 中增加 `markings`，单测退出 1（1 failed、3 deselected）。当前生产者仅保存 16 项，Handoff hash、Task.goal、Brief.spec 与预期不一致。
- 最小改动：仅 accepted-stage 分支 `sourceLineage` 增原命令 `markings`，v3 现为 17 项。原 Issue v1/v2 分支未修改。
- 专项与相邻回归：四个文件 55 passed，退出 0；隔离 PG 由现有 pytest conftest 建立/销毁，当前命名库只作 preflight 身份读取，无业务写。`py_compile` 退出 0，`git diff --check` 退出 0。
- 一致性复审：231-5 §9 要求 Task.goal、Brief.spec、Handoff 同源及后续原 Owner 重验；新增字段进入 Task/Brief/Handoff hash 和同 key 幂等比较。旧分支字段/哈希保持原样。
- 边界：本波仅补来源保真；原 Host `revalidate/execute/Receipt verify`、包内新生成端口仍关闭。没有真实生成、Provider 调用、人工评审或自然首链证据。当前正式 OIDC/Host 身份、八配置、Growth1.13 发布、binding/assignment 仍独立缺口。

下一步 d2b2：为宿主生成入口建立 v3 严格命令与原 StageDecision/Eval/permission、GrowthPlan、Task/Brief 的 Owner 回读 RED；可读 Artifact/人工评审消费者齐备前继续禁入。再独立以最新代码重启受限 PG/API/Web 并回读八工作台，不把禁入预览当业务完成。
