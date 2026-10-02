# E17-a2b2b2 当前正式来源只读审计

## 复习与范围

接 `AOS-001148`、E17-a2b2b1 selector 与 231/E17 正式启动方案；本轮只读核对本机当前环境和 `ai_agent` 浅层文件名，不读取凭据内容、不修改真实库或准入开关。该扫描范围不证明全机不存在其他外部授权材料。

## 新鲜证据

| 项 | 命令/结果 |
| --- | --- |
| OIDC | 当前执行器环境 `AOS_OIDC_JWKS_URL(S)`、`AOS_OIDC_ISSUER(S)`、`AOS_OIDC_AUDIENCE` 均 unset；`--serve-limited --api-identity-file /nonexistent/identity.json` 退出2 `EXTERNAL_OIDC_CONFIG_REQUIRED`。 |
| Host 凭据 | `a0v_current_runtime_host_preflight.py --signed-receipt ...` 未给 credential file 退出2 `CREDENTIAL_FILE_REQUIRED`。`ai_agent` 最深四层文件名扫描仅见 `aos-recovery/.aos-testonly-bg00cf-3r_lw6yp/api-service-identity.json`，明确 test-only，不可接当前实例。 |
| 签名来源 | `.env` 的 `AOS_BUNDLE_ROOT` 指向存在的本机 pinned preview signed tree；`AOS_BUNDLE_TRUST_ROOTS_FILE` 指向已不存在的 09-10 canonical 路径。重启脚本自身会以当日 pinned signing receipt 覆盖预览进程的两项值，故本机预览仍 GREEN。此 `.env` 漂移是独立配置债；不能仅把它改成 Growth1.13 本地测试 trust 并称正式来源。 |
| 现存签名文件 | 顶层当前 pinned preview receipt/trust，与 `aos-recovery` 内 Growth1.13 本地 signing receipt/trust 可核验；它们分别是预览与隔离 test-only 证据，均非当前正式 signer/checker/外部 trust 授权。 |
| 实例事实 | 当日最新 PG/API/Web 预览重启见 `w5cb4-daily20261002-latest-68c-restart-verification.md`。当前只读对账 binding/assignment/identity/operation=0；八配置、Growth1.13 当前发布仍沿当日正式来源审计的0值，没有任何本轮写入。 |

## 结论与下一安全路径

E17-a2b2b1 的 selector 可验证**已提供的**签名 source/lock/OCI，但正式来源的归属和供给仍无正向证据。受限 API/Host 直接接任意文件路径会允许本地 test-only trust 冒充正式 authority；本轮不改 `--serve-limited`、Host 或 `.env`，不启 Host/worker/Provider。当前实例的正式启动接线保留 E17-a2b2b2 待办，需外部 OIDC、正式 trust/root/Receipt、独立身份与 Owner/八配置来源；局部缺口不停止 Goal。下一波转已登记的八类配置合法生产者或 d2b3c4f 原 Review Receipt 独立代码链，先方案/RED 后最小实现。
