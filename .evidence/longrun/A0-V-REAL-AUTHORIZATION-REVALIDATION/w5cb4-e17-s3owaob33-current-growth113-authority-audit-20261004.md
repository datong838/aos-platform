# E17-s3o-w-ao-b33｜当前 Growth1.13 正式来源与配置候选复核

## 核对范围与判据

只读比对当前 `.env` 的签名根、原 Registry、Installation、Host assignment，以及 1.13 本地签名脚本/Receipt 的作用域。判据是同一当前实例存在可由原 Registry/安装链证明的 Growth1.13 发布、有效签名/OCI/trust、active/current 同代绑定与精确 Host Owner；本地 test-only 签名不得转用。再检查 D-waves s3e–s3i 是否已有隔离代码正链，避免重复开发。

## 现场结果

- `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：当前库 `aos_current_preview_20260927`、代码/库 `a0v_135`、approved 安装、四发布、runtime Binding0。该预检只证明旧预览的当前签名一致。
- 当前 `AOS_BUNDLE_ROOT` 的 Growth 子目录只有 `1.11.0`。原库 `BEGIN READ ONLY` 查 `asset_bundle_version`：`solution.ecommerce.growth|1.11.0|published|sha256:3d8817…02b328`，无 1.13；`extension_runtime_host_assignment` 0，Installation active revision仍NULL。`select_formal_current_release` 代码要求 Growth `1.13.0` 以及 `read_current_runtime_image_evidence` 的 active/current 同代事实，当前路径未满足。
- 仓外 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-growth-113-signing-receipt-20261002-r1.json` 存在，`SIGNED_TREE_GREEN`、local signedTree 指向隔离目录；`scripts/sign_ecommerce_growth_1_13_candidates.py` 明示 local isolated signer、`registryPublishCount=0`、`installationMutationCount=0`。先前隔离 PG/OCI 正例只能证明流程能力，不能证明当前实例发布或 Owner。未读取签名私钥或商城源。
- D-waves b14 与 s3e Guard 清单已经登记 s3e–s3i 原签名/审批/低权配置候选的隔离 +1；复写同样的 +1 不产生当前正式配置。下一独立研发入口应是共享 Receipt operation/会话正式协议和当前安装来源接线，或正式身份生产者具备后进行受控发布；本棒不造新 helper/不把测试身份升当前 authority。

## 判定与风险

当前 Growth1.13 正式来源链未满足，Host/worker/Provider 继续关闭，八配置/六 Binding/自然首链仍 pending。此波只读审计，无 RED/生产代码/当前库写，不能当成业务进度通过。b31 新生产代码仍待每日完整重启加载；收到提醒时执行一次最新栈重启，不以本预检替代。
