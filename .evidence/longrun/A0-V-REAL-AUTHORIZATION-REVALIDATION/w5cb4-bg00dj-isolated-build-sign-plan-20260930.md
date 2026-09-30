# W5CB4 BG00dj｜growth 1.12 独立 build/sign 文件级方案（进行中）

## 已读上位与具体差距

231-2 禁改既有 release，需隔离 OCI、依赖锁、SBOM、评估和签名逐项证明。BG00di 的 1.12.0 只有 `UNBUILT_UNSIGNED` 候选。现有 `build_ecommerce_current_candidates.py`/`sign_ecommerce_current_candidates.py` 固定 growth 1.11.0；底层 builder 的 `_augment_sbom` 要求源 `evidence/sbom.json`，而 BG00di 有意移除了旧版 SBOM。因此直接使用当前 profile 会错误选旧版或因缺 SBOM 失败。

## 最小实施设计

1. `scripts/build_ecommerce_growth_1_12_candidates.py` 单独加载 current builder，精确断言 growth 1.11.0 唯一且 operation count 15，然后只替换为 1.12.0。保持 core/Niushop/operations-base 的固定版本与当前 profile 不变。对复制到隔离 build 输出的 growth 成员，使用 hash `ac64aec9…9d5e` 锁定的 1.11.0 基础 SBOM 数据组件，追加 `business-investigation.readonly` 数据组件，再调用原 builder 的 OCI/SBOM 增强；源候选仍保持 unsigned/unbuilt。
2. `scripts/sign_ecommerce_growth_1_12_candidates.py` 单独加载现有签名器，固定新 build profile 和独立测试签名 keyId；复用原严格 build receipt、source hash、输出目录与四包签名检验。所有签名状态与 build 输出在 repo 外新目录；不复用当前 `.aos-current-build-*`、现有签名根或正式身份。
3. 先在 `services/aos-api/tests/extension_runtime/` 写 RED：新 profile 精确选 1.12.0、旧 current profile 仍 1.11.0；SBOM 缺项/源 hash 漂移拒绝；错误 build receipt、仓库内目标、既有 state 不写；候选模板字节漂移应在 source/preflight/hash 链中被识别。
4. 最小实现后跑新旧 build/sign 相关专项，条件满足时在 `colima-aos-extension` 做隔离 build、qualification 与签名；每一步原始 receipt/hash/退出码落盘。若引擎或资格证明缺条件，不伪称签名，通过代码和候选独立波继续推进。

## 边界

不写当前 DB、不改当前签名树、不做 Registry publish、安装、Host/worker/Provider 或旧 Run。开发测试签名只能证明供应链机制，不能充正式组织批准、当前三身份、Owner、配置或首链。

## 首次 build 后的实际失败与方案修订

隔离 Colima build exit 0 `BUILD_GREEN`，但资格验证在 `ReleasePolicy._assert_release_evidence` exit 1：新 1.12.0 候选缺少本版 `evidence/bundle-evals.json`，符合先前 `UNBUILT_UNSIGNED` 设计。不得复用 1.11.0 的旧 eval，也不得绕过 ReleasePolicy。

本波补充文件 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.12.0/evidence/bundle-evals.json`：先重新跑本版候选/模板/build-sign/旧版兼容测试，以实际命令和结果记录 source/contract evaluation，`runtimeReadiness` 仍为 `blocked`，明示正式签名/安装/身份/自然业务未证。加入此文件后 source hash 改变，旧 build/receipt 保留为失败现场，用新隔离目录重新 build/qualify。新签名入口还应要求同一 build 的 `QUALIFICATION_GREEN` receipt（hash、output tree、git HEAD、resolved 1.12 与无效果字段一致），缺项拒绝；不能仅凭 `BUILD_GREEN` 签名。
