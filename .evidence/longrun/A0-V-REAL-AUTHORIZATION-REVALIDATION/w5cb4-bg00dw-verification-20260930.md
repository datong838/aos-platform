# W5CB4 BG00dw｜签名 BI Plan 只读准入投影验证

## 范围

按 `w5cb4-bg00dw-exact-bi-admission-plan-20260930.md` 新增服务端 GET 只读快照。请求只收 `installationId`，Principal 由认证依赖提供。读服务先核验同租户正式 OIDC、远程权限适配器禁入、当前持久成员/控制角色，再读安装与 lock markings；marking 不满足时隐藏安装。签名 approved 模板使用现有 resolver，六实例只读 active 版本。返回 `candidateReady` 仅为瞬时建议，`writeRevalidationRequired=true`；原 POST 的锁/权限/签名/实例/Receipt 事务不变。

| 证据 | 命令与结果 |
| --- | --- |
| RED | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py -k signed_bi_admission --disable-warnings --tb=short` → exit 1，缺 `SignedBIPlanAdmissionReader`；随后最小实现。 |
| 专项 | 同命令 → exit 0，7 passed；错租户/dev token、无成员/低角色、远程鉴权适配器、marking 无权与缺签名/六实例均保持禁入。 |
| 相邻累计 | BI 权威/就绪/组合、签名模板、W2A/W2B Store、当前权限七文件 pytest → exit 0，92 passed / 49 skipped；`py_compile` 与 `git diff --check` exit 0。日志 `/tmp/aos-bg00dw-adjacent-final.log`。 |
| OpenAPI | `app.openapi()['paths']['/v1/aip/production-contracts/responsibility-plans/bi-preparation/admission']` → GET、200 schema 存在，exit 0。 |
| 当前/clone 正式来源 | `scripts/a0v_growth_112_formal_source_audit.py --current-signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json --successor-signed-receipt /Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r3-20260930.json` → exit 0、`effects=0`、`formalReady=false`。当前 `a0v_118`、growth1.12=0、Host identity/assignment=0、八候选全0；clone growth1.12=1，但 Host/配置同样未齐。原始输出 `/tmp/aos-bg00dw-current-audit.json` 最后一行。 |

## 复审与限制

读连接使用 scoped repeatable-read/read-only；安装和签名 resolver 分别读取，可能跨快照，故输出只叫候选，绝不当作写或运行权威。正式 OIDC 正向当前不可用，本波未用假账号调用当前实例 GET，也未写当前/clone DB、Receipt 或启动 Host/worker/Provider。当前真实首链仍 pending。browser-pilot 不可调用，且本波未接 UI，浏览器验收留至 BG00dx。

下波 BG00dx：在运行实例/职责计划页消费 GET 的精确阻断，认证不足时不可枚举；只有服务端候选且当前强 ETag 匹配时才呈现受控提交，但正式当前权限、签名与六实例齐备前始终禁入。受控提交的未知结果必须只读对账、沿用同一幂等键，不自动重发。
