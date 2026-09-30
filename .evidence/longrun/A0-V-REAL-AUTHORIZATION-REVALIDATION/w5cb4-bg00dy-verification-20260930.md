# W5CB4 BG00dy｜签名 BI Plan 原命令 Receipt 只读对账验证

## 方案与实现

先复习 231-3/231-9、BG00dw/dx、Plan 命令事务与 Receipt 表；文件级方案见 `w5cb4-bg00dy-controlled-plan-command-plan-20260930.md`。本波新增认证 GET，只读查询固定 `bi_responsibility_plan.prepare`、当前租户、原 actor 和原幂等键。查询前要求正式 OIDC、当前持久成员及配置角色；远程权限适配器不可校验时拒绝。返回原 Receipt 的哈希和精确 Plan ref，明确 `installationBindingVerified=false`。404 仍是 unknown，不授权重发。前端只加 SDK 严格解析，不提供写按钮或自造幂等键。

## 可复核证据

| 检查 | 命令及结果 |
| --- | --- |
| RED | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py -k signed_bi_receipt_readback --disable-warnings --tb=short` → exit 1，3 failed：Reader 未实现。 |
| 后端专项 | BI authority/readiness/composition、签名模板四文件同一 pytest → exit 0，78 passed。 |
| 原 W2 Store/API | W2A Store、W2B API/Store 三文件 pytest → exit 0，23 passed。 |
| 前端专项 | `vitest run src/api/aipProductionContracts/parser.test.ts src/api/aipProductionContracts/index.test.ts` → exit 0，27 passed；`tsc --noEmit -p tsconfig.json` → exit 0。 |
| 前端累计 | `vitest run` → exit 0，314 files / 2741 tests passed。 |
| 合同 | `app.openapi()` 精确 GET 路由存在，exit 0；`git diff --check` exit 0。 |

## 复审与风险

本波只读、不写当前/clone DB，不启动 Host/worker/Provider。Receipt 旧表未独立保存原 installation ID/ETag，故命中也不能证明原安装绑定，更不能证明当前可执行。当前正式 OIDC、签名安装、六 active 实例与三身份/Owner 仍待当前实物核验；未用测试 Principal 冒充正式身份。browser-pilot 当前不可调用，页面截图待工具可用时补。

下波 BG00dz：审查现有写命令的未知结果重放次序与 Receipt 原安装绑定缺口，先文件级方案和 RED；若需新增持久字段，单列迁移、备份、克隆全链与零执行窗口，不写当前真库。并行只读核验正式 signer/checker、三身份、Host assignment/Owner、八配置候选；只有当前授权完整才考虑有界 Host 与自然首链。
