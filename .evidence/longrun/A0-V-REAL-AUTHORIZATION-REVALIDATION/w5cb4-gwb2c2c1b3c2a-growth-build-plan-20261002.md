# GW-b-2c2c1b3c2a｜Growth 1.13 独立构建与资格

2026-10-02 09:46 CST。基线 `aos-platform/m1 89feb64a`、Authority `AOS-001117`，已复习 231-2 制品/供应链、231-5 §9、D-waves GW-b-2c2c1b3c2、原 1.12 构建与隔离签名器。当前 1.13 是未构建、未签名候选，1.12 已签制品与正式当前实例不可覆盖。

## 文件级计划

1. 新 `scripts/build_ecommerce_growth_1_13_candidates.py`：复用原 `build_ecommerce_current_candidates.py` 的隔离构建器，只替换 Growth 1.11 坐标为 1.13，锁 `EXPECTED_RUNTIME_OPERATION_COUNT=15` 与 1.13 源树 hash。仅在输出副本增补已审 1.11 SBOM 中的 BI 只读组件，再调用原 runtime SBOM 增补；不修改任何历史 profile 或候选原树。
2. 新 `services/aos-api/tests/extension_runtime/test_build_ecommerce_growth_1_13_candidates.py`：先 RED 缺 profile；完成后核四包坐标/8 工作台/15 总 operation、1.13 源 hash、SBOM 输出单份 BI 组件且源不变、旧 1.12 profile 原结论不变、源漂移与基线 SBOM 漂移拒绝。
3. 若专项通过，用隔离 `colima-aos-extension` 原 build/qualify CLI 对仓外唯一新目录生成 build 与 qualification Receipt，回读 image/config digest、schema/SBOM/依赖锁及七项篡改拒绝，作用计数全零。输出只用于测试与审计，不注册、安装、迁移当前库或启用 Host。任何构建失败保留原始输出，先只读对账再决定重试；不重用旧 1.12 签名。

## 退出与风险

专项/相邻回归、`py_compile`、`git diff --check`、原 builder Receipt 核验；逐项记录测试与 OCI。此波不做正式签名/发布：本地生成物不是当前正式信任根；签名与正式八源/Owner 下一切片。当前 DB `a0v_118` 只读，今日最新版本完整重启仍待独立零执行窗口、停机备份与身份门。

## RED 修订（09:50）

第一份隔离 build `BUILD_GREEN`，但原 qualifier 在 `ReleasePolicy._assert_release_evidence` 失败：1.13 源候选因不复用旧 1.12 的评测文件，build 输出缺 `bundle-evals.json`。失败发生在 OCI qualification 前，资格 Receipt 未生成；首次 build 与 Receipt 留在仓外作反证，不覆写。不能把旧 1.12 report 复制给新源码，也不修改已提交的 1.13 源候选。

文件范围补本波 `.evidence/.../w5cb4-gwb2c2c1b3c2a-growth-113-bundle-evals.json`：以本轮实际测试命令/退出码记录仅“候选源码和合同通过”，`runtimeReadiness=blocked`；profile 锁该报告 hash，仅在独立 build **输出副本**写入，不污染 immutable 1.13 源。原 builder 将此报告纳入 build content hash，后续原 qualifier 再读取。先运行新鲜合并专项并写报告，再补 profile 与负测，使用全新唯一 build 目录/Receipt 重建；原失败制品只读保存。没有真实模型效果或正式业务证据，报告不得宣称可运行。
