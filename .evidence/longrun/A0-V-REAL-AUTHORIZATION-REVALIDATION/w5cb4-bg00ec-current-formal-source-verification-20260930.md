# W5CB4 BG00EC｜当前正式来源与 Host 目标只读核验

## 现场与命令

先按 `w5cb4-bg00ec-current-formal-source-plan-20260930.md` 复习 231-2/231-3、BG00ci/dn，未改生产代码。当前 m1@8386cce1、权威 AOS-000990。输出只含来源状态和计数，不含凭据或成员 subject。

| 检查 | 命令/定位 | 退出码与事实 |
| --- | --- | --- |
| 当前+克隆固定源 | `services/aos-api/.venv/bin/python scripts/a0v_growth_112_formal_source_audit.py --current-signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json --successor-signed-receipt /Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r3-20260930.json` | 0；`/tmp/aos-bg00ec-formal-audit.json`：两库 a0v_118，当前 growth1.12=0、克隆=1；Host identity/assignment 当前0，八类候选当前与克隆均0；`effects=0,formalReady=false`。 |
| 原 Host 只读预检 | `services/aos-api/.venv/bin/python scripts/a0v_current_runtime_host_preflight.py --signed-receipt .../signing-receipt.json` | 2，`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`；没有启动 Host。 |
| 当前启动键名/路径存在性 | 仅解析 `.env` 的键名和路径存在性，不打印值 | 0；`AOS_BUNDLE_ROOT` 有效；`AOS_BUNDLE_TRUST_ROOTS_FILE` 路径不存在；`AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE`、OIDC issuer/audience/JWKS 键缺。 |
| 旧 Host 启动器目标 | `rg -n '^DATABASE =' scripts/a0v_ecommerce_runtime_host_bootstrap.py` | 0；固定 `aos_meta_head`，与当前 `aos_current_preview_20260927` 不同，不可拿旧启动器补当前 Host。 |
| 生产写入路径静态核查（BG00ED 复核修正） | `rg -n 'def publish_policy|publish_policy\(' services/aos-api/aos_api/aip_model_runtime_store.py services/aos-api/aos_api/routers/aip_model_runtime.py` | 0；`AipModelRuntimeStore.publish_policy` 与正式 API 路由均存在。此前仅搜显式 `INSERT`，漏掉 `_publish` 通用写入，故“生产 writer 未定位”的判断撤回。已有代码路径不等于当前实例具备发布权限或完整依赖。 |

## 八类候选的当前 Owner 路径

`runtime_configuration_candidates.read_candidates` 只数当前 head+revision 且冻结/active/有效期满足的行；计数不是安装绑定或授权。

| 候选 | 已有受检来源路径 | 当前数 |
| --- | --- | ---: |
| `responsibility_plans` | `AipProductionContractStore` 的 Plan 创建/冻结；BI 原命令仍要求正式签名模板/六实例/actor | 0 |
| `runtime_policies` | 生产 Owner 为 `AipModelRuntimeStore.publish_policy`，路由为 `aip_model_runtime.publish_policy`；读取器 `configuration_source_catalog`/`aip_runtime_configuration_sources` | 0 |
| `data_policies`, `egress_policies` | `aip_runtime_guard_policy_store.py`；需当前 active、有效期和精确用途 | 0 / 0 |
| `network_policies` | `aip_network_policy_store.py`；受网络审批/独立 checker 与签发门约束 | 0 |
| `quota_policies`, `budget_policies` | `aip_model_governance_policy_store.py`；需当前 active 与有效期 | 0 / 0 |
| `budgets` | `aip_budget_store.py`；需当前 active 与有效期 | 0 |

## 结论与下波

BG00EC 的只读核验 GREEN，当前实例正式授权依然失败关闭。缺当前签名 growth1.12 与信任根、独立 checker、三身份文件、Host identity/assignment、八候选；当前一名成员不能替代独立 checker。没有证据允许当前真库写入、开启 Host/worker/Provider 或自然首链。下一波 BG00ED 复核既有生产 Owner 与依赖、权限/幂等/版本合同，再出文件级方案；只在隔离克隆做合法来源准备与拒绝测试，不手工往当前库插行。当前数据库迁移/身份切换仍须独立备份、完整克隆演练及零执行窗口。

本波无代码写入，不需 mock 测试代替正式证明；browser-pilot 不适用。真库只读、不读商城源、不写 dev-org、不回放旧 12 Run、不手工 run_definition、不 push，230 L0 挂起。
