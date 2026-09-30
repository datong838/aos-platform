# W5CB4 BG00ea｜签名 BI 原命令绑定联合读回验证

## 变更与语义

先按 `w5cb4-bg00ea-receipt-readback-plan-20260930.md` 复习 231-3/231-9 与栖月汇方案。认证 GET 仍要求同租户正式 OIDC、当前持久成员及配置角色，固定 BI operation/原 actor/幂等键。旧 Receipt：`installationBinding=null`、`installationBindingVerified=false`；新 Receipt：严格验证同事务存储的原安装 UUID/ETag/exact 模板/actor，返回该绑定并标 true；畸形/错 actor 拒绝。两种情况都固定 `currentAdmissionVerified=false`。前端 SDK 只 GET，严格校验字段关系、UUID/ETag/模板/哈希/时间；页面没有新增写按钮或自动重发。

| 检查 | 命令与结果 |
| --- | --- |
| RED | 后端 `pytest -k signed_bi_receipt_readback_is_actor_scoped` → exit 1，DTO 缺原安装绑定；前端专项曾 1 failed，解析器拒绝新绑定。 |
| 后端专项 | BI authority/readiness/composition、签名模板、W2A/W2B Store/API 七文件 pytest → exit 0，102 passed。 |
| 前端专项 | `vitest run src/api/aipProductionContracts/parser.test.ts src/api/aipProductionContracts/index.test.ts` → exit 0，28 passed；`tsc --noEmit -p tsconfig.json` → exit 0。 |
| 前端累计 | `vitest run` → exit 0，314 files / 2742 tests passed；日志 `/tmp/aos-bg00ea-vitest.log`。 |
| 接口/静态 | OpenAPI 精确 GET 200 响应存在，exit 0；`py_compile`、`git diff --check` exit 0。 |
| 当前正式来源 | `scripts/a0v_growth_112_formal_source_audit.py --current-signed-receipt ... --successor-signed-receipt ...` → exit 0，`effects=0`、`formalReady=false`；`/tmp/aos-bg00ea-current-audit.json`。当前库 `a0v_118`，growth1.12=0，Host 身份/assignment=0，八类候选均0；独立 checker/三身份引用缺。 |

## 复审与限制

`installationBindingVerified=true` 仅表明可信 Receipt 中记录了**原命令**绑定，不证明 Plan 当前状态、安装当前准入或运行授权；`currentAdmissionVerified=false` 强制保留。旧 Receipt 不回填、不猜测；404/网络未知不授权重发。真库/clone 未写、Host/worker/Provider 关闭。正式 OIDC 正向当前不可用，不用测试 Principal 冒充当前实例成功；browser-pilot 当前无 callable 工具，页面截图待可用后补。E17 真实首链仍 pending。

下波 BG00EB：只读核对 Receipt 中的 Plan exact ref 与持久 Plan revision/actor/hash，明确旧/新 Receipt 丢失或漂移的失败边界；再复习产品页面的未知结果恢复入口，不生成或重发命令。
