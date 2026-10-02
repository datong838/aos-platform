# GW-b-2c2c1b3c1｜当前后端的不可变 Growth 1.13 候选

2026-10-02 09:24 CST。基线 `aos-platform/m1 14d6647f`、Authority `AOS-001116`。本切片只形成未构建、未签名候选；正式信任根、OCI 构建、配置八源、首登记 Owner 和当前实例授权另门证明。

## 上位与现场

- 复习 231 主计划安装/启用与签名边界、231-5 §9 已接受阶段来源、231-9 首链与八台验收，以及 D-waves GW-b-2c2c1b3c。原 1.12 签名包后端比今日工作源码少 `analyst_structure_eval_operation.py`，另有 `__init__.py`、Handoff、Review command、Content workflow contracts 共四处差异；38 个其余 Python 文件一致。
- 1.12 候选目录树 hash `5175c24ccd010428e5c4cf54c6cee9d92ec8ccb4cc9ccb92a5c88a55288e0017`，不修改它及其已签归档。manifest 实际为 10 个 `ecommerce_growth_*` 加 1 个 `analyst_workspace_view_v1`，共 11 个 API operation；D-waves 的“九 API”是旧口径，本切片按原 builder 的 manifest/registration 精确一致性验收。当前权威库仍 `a0v_118` 且只读，代码头 `a0v_135`，Host/worker/Provider 禁入。

## 文件级计划

1. `scripts/prepare_ecommerce_growth_1_13_candidate.py`：只读锁定 1.12 候选树和当前后端 5 个 exact SHA256；确认差异集合恰为这 5 个文件。复制为新 1.13 staging，改唯一 manifest 版本与八个 workshop 自引用；仅覆盖这 5 个后端文件；移除旧构建/签名产物，写明 `UNBUILT_UNSIGNED` 的来源证据。目标已存在或源漂移则拒绝，原子发布新目录。
2. `services/aos-api/tests/extension_runtime/test_ecommerce_growth_1_13_candidate.py`：先 RED 验证新目录尚不存在；实施后核 manifest/registration 的 11 个精确 API、Schema requirement/compatibility、五文件与当前源码同 hash、其他历史文件仍同 1.12、八自引用、无签名或 runtime image、源目录不变、重复生成拒绝及 drift 拒绝。
3. `bundles/candidates/ecommerce/solution.ecommerce.growth/1.13.0/`：脚本唯一生成输出，保留既有 schema/资源内容与旧 1.12；不手改历史包。

## RED 修订（09:30）

按本计划增加的原 builder 精确 manifest/registration 检查失败：当前后端 `__init__.py:register` 返回 11 个 API，却遗漏旧 1.12 已有的 14 个 navigation/UI 静态贡献；候选 manifest 仍声明这些项，原 `_runtime_registration` 正确拒绝 `MANIFEST_RUNTIME_API_MISMATCH`。这不是可忽略的“九 API”口径问题。文件范围补 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py`，仅恢复原 1.12 的 `_STATIC_CONTRIBUTIONS` 与 `register` 拼接，不改 API dispatch。随后刷新准备器中此文件的 exact hash，并仅重建本波尚未提交的 1.13 输出；1.12 源和已签包不动。先保留此 RED，再完成最小修复与相邻回归。

## 验收与下一门

专项新测试和相邻 1.12/preflight 测试、`py_compile`、`git diff --check`。当前候选可供下一波独立 build/qualify/sign/OCI 受理；**候选未签名不能发布或安装**。下一波复核正式八类配置候选及首登记 Owner；缺当前正式身份时只阻断实例，不影响独立研发。此波不访问商城源、不写当前 DB、不启动 Host、不做人工 Run 或旧 12 Run 重放。
