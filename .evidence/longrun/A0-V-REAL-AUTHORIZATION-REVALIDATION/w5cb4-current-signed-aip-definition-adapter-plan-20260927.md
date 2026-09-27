# W5CB4 当前签名 AIP 定义适配第一切片（2026-09-27，编码前）

## 上位与结论

- 231 BG-00/03/04、`w5cb4-current-signed-aip-definition-publication-feasibility-verification-20260927.md`：当前 signed growth `1.11.0` 内容有完整 6/37/10，但旧 `AipSolutionPackPublisher` 和 installer 只认 `1.3.0` 包／`1.2.0` 来源。本切片只把**读取与来源选择**改为双版本兼容，不发布当前库、不开 Runtime。
- 旧 `publish(bundle_dir, actor)` 行为保持：仍只接收 `1.3.0`，来源 `1.2.0`。新入口必须显式指定 `1.11.0`，并在生产调用前由下一切片 Registry/TrustRoot exact 验证；本切片不暴露可任意发布未签名目录的对外命令。

## 文件级

1. `services/aos-api/aos_api/aip_solution_pack_publisher.py`：将纯校验/载入中的版本判断参数化为局部 `expected_bundle_version`，为下一切片提供当前版本解析校验；不改变现有 `publish` 写路径与签名假设。分析模板 bundleRef 必须随解析版本 exact 匹配。
2. `services/aos-api/aos_api/aip_ecommerce_agent_installer.py` 的来源选择暂不改：在未完成签名/Registry 前置前切换 installer 会让未验证定义成为页面权威，故纳入下一切片。此处先固定“不跨 6/37/10 来源混拼”的后续验收条件。
3. `services/aos-api/tests/aip/test_aip6_ecommerce_solution_pack.py` 专项：旧行为回归、当前包只读解析 6/37/10、错版本/分析模板漂移拒绝。代码只读/纯逻辑，不访问当前业务库。
4. 专项测试、累计回归、方案/代码一致性复审、verification→m1 提交；下一波才做签名来源 exact preflight 和真正写入。

## 停止条件

- 若 parser 与 publisher 当前耦合不能在小改动下隔离，不为了跑绿放松旧 `publish` 版本门；冻结并给下一切片精确设计。无当前 DB 写、SQL 填行、Provider/商城源/worker。
