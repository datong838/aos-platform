# GW-b-2c2c1b3c1 验证：Growth 1.13 当前源码候选

2026-10-02 09:41 CST；基线 `m1 14d6647f` / `AOS-001116`。Task Receipt `W5CB4-GWB2C2C1B3C1-20261002` 及登记入口修复 `W5CB4-GWB2C2C1B3C1-REG-20261002`。方案 `w5cb4-gwb2c2c1b3c1-growth-successor-plan-20261002.md`，已补 RED 根因。此波不触碰当前库、Host/worker/Provider、商城源或旧 12 Run。

| 门 | 命令及本次结果 |
| --- | --- |
| 源差异 | `sha256` 对当前后端和旧已签 1.12：4 个同名文件变化、1 个新文件、其余 38 个 Python 文件同 hash。准备器锁定 1.12 候选树 `5175c24c…5288e0017` 与 5 个当前文件 hash。 |
| RED | 新候选测试最初 2 failed（准备器不存在）；生成候选后，原 `_runtime_registration` 拒绝 `MANIFEST_RUNTIME_API_MISMATCH`：今日 `register()` 漏掉 14 个原 navigation/UI 贡献。 |
| 最小修复 | 当前 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py` 只恢复旧 1.12 的 14 个静态贡献，仍保留今日 11 个 API 及 `evaluate_stage_structure` handler。准备器 exact hash 刷新；删除并重建仅本波未提交的无签名 1.13 暂存目录。 |
| 新候选 | `python3 scripts/prepare_ecommerce_growth_1_13_candidate.py` 退出0：八个 workshop 自引用改到 1.13；树 hash `5818e50bd8c28900ec324b023243b8289a4ef243413b51fd94437fb7fa1f3167`；1.12 源树 hash 不变。原 builder 核 manifest/registration 11 个 API 和 schema compatibility 通过。 |
| 回归 | `services/aos-api/.venv/bin/pytest -q --disable-warnings` 精确跑新 1.13、旧 1.12、旧 build profile、Eval operation、registration contracts 五文件：`51 passed, 8 warnings`，退出0。`python3 -m py_compile` 三文件及 `git diff --check` 退出0。 |

复审：1.13 `content-source-provenance` 明示 `UNBUILT_UNSIGNED`；没有 `bundle.signature.json`、SBOM、runtime image index、bundle eval；旧 1.12 候选与历史已签树未改。当前包的静态贡献修复与 manifest 原 14 条相等；源候选五文件同今日源码，其他文件仍来自旧 1.12。方案的“九 API”历史口径被本次现行 manifest 证伪，现行是 10 个 `ecommerce_growth_*` 加 1 个 `analyst_workspace_view_v1`，共 11 个 API。

结论仅为**未构建、未签名、未安装的当前源码候选**及当前注册合同修复。下一波需要新 profile 的 build/qualify/OCI/签名来源，再核八类当前配置与首登记正式 Owner。测试本地签名不等于正式信任根；当前真实 DB `a0v_118` 对代码头 `a0v_135` 的完整重启仍未执行，正式首链仍待证。
