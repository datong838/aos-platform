# W5CB4 BG00EB｜签名 BI Receipt→Plan 与未知结果只读入口验证

## 方案、实现和边界

依据同目录 `w5cb4-bg00eb-receipt-plan-and-recovery-plan-20260930.md`，服务端仍在正式 OIDC、当前持久成员/配置角色、租户/operation/原 actor/原幂等键约束下读 Receipt。新增同一 `connect_read_only` repeatable-read 连接的持久 Plan revision 查询，精确核对 tenant、plan_id、revision、hash、created_by；新 Receipt 还核对原 template exact ref。丢失或漂移以 503 fail-closed。旧 Receipt 不倒推安装绑定。返回 `planRevisionVerified=true` 仅证明读取时 Plan 原修订匹配，`currentAdmissionVerified=false` 仍固定。

前端在有效来源安装上下文允许用户手输**已有原键**并主动点击只读 GET。无键/非法键不请求；键不入 URL 或持久存储，不生成键、不 POST。旧绑定缺失、跨安装、403/404/网络未知都不能显示当前已配置或可运行；输入或来源切换清理旧结果。此入口不是 BI 配置提交。

| 检查 | 命令/输出 | 结论 |
| --- | --- | --- |
| 后端 RED | `pytest -q ... -k signed_bi_receipt_readback_is_actor_scoped` | exit 1，缺 `plan_revision_verified`；预期失败 |
| 前端 RED | `vitest run ...parser.test.ts ...index.test.ts`；`vitest run ...ProductionContractsPage.test.tsx -t '只有用户输入原始键'` | 均 exit 1，分别因解析器未拒绝 false 与页面无入口；预期失败 |
| 后端专项 | `pytest -q ...test_ecommerce_business_investigation_aip_authority.py -k signed_bi_receipt` | exit 0，5 passed；含旧/新 Receipt、缺 Plan/hash/actor/template 漂移及权限拒绝 |
| 后端累计 | 九个 BI/W2A/W2B/模板相邻文件 `pytest -q --tb=short` | exit 0，109 passed；日志 `/tmp/aos-bg00eb-pytest-cumulative.log` |
| 前端专项 | `vitest run parser.test.ts index.test.ts ProductionContractsPage.test.tsx` | exit 0，53 passed，含原键手动触发、非法键、错安装、404 和换键清空 |
| 前端累计 | `vitest run` | exit 0，314 files / 2744 tests；日志 `/tmp/aos-bg00eb-vitest.log` |
| 类型与静态 | `tsc --noEmit -p tsconfig.json`、`python -m py_compile`、`git diff --check` | 均 exit 0 |
| 正式来源 | `scripts/a0v_growth_112_formal_source_audit.py` 按已签名当前/后继 Receipt 只读核查 | exit 0，`effects=0`、`formalReady=false`；`/tmp/aos-bg00eb-current-audit.json`。两库 a0v_118；当前 growth1.12=0、Host identity/assignment=0，八类候选均0 |

## 复审与未完成

只新增一个 Plan SELECT，无新表、迁移、锁、命令或后台自然消费。当前真实库没有正式新 BI Receipt 正向实例，因此服务端真实生产正向仍未验证；测试只证明实现分支与拒绝边界。browser-pilot 工具当前未提供，未做浏览器截图，不以 jsdom 代替。正式签名制品、当前信任根、独立 checker、三身份凭据、Host Owner/assignment、八类配置候选未齐，E17 首链仍 pending。Host/worker/Provider 不开启；当前真库只读，不读商城源、不碰旧 12 Run、不手工 run_definition、不 push、230 L0 挂起。

下波 BG00EC：继续正式签名发布/信任根/独立 checker 与三身份来源的当前可复核审计，明确当前 Host assignment/Owner 与八配置候选的最小供给路径；若缺合法 authority，仅阻断该实例，转做可独立完成的产品/代码切片，不借本波 Receipt 对账开启运行。
