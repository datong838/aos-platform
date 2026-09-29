# W5CB4 BG-00ar｜正式 G2 评测来源与对象字节链只读审计

## Rules/方案

按 231 主计划、G2.2、AIP-4 三层门和 BG-00ap/aq 的现有边界，只读定位正式 G2 Dataset source kinds、字段白名单/用例数、脱敏 Receipt 生产/撤销 Owner，以及有界 S3 字节读取器如何接入 Store/Writer。不得用测试 selection、占位文件、旧 Logic Eval、单独 Artifact metadata 代替当前真实来源。当前库不写、商城源不读、Host/worker/Provider 不启。

## 文件级步骤

1. 读 231、228 G2.2、AIP-4 Eval、R25 合同、当前签名 growth `evals/placeholder.json` 与 Eval Manifest/Store/Runner/Object reader，精确写出明确/未冻结的 source kinds 与 Owner。
2. 当前库只读查 Eval Artifact/Dataset/Suite/Receipt 与签名 placeholder；核固定 MinIO image/19000，不取真实对象字节。判明现有对象读取器是否被运行链调用。
3. 输出下一独立代码门文件级计划或外部 authority 条件，记录未关闭风险。只读波无需伪造 RED 或业务验收。
