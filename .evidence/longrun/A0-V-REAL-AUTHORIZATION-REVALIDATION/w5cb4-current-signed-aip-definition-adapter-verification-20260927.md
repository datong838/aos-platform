# W5CB4 当前签名 AIP 定义适配第一切片 verification（2026-09-27）

## 结果

- 在 `AipSolutionPackPublisher` 增加 `inspect_current_candidate(Path)`：仅解析本地候选内容，明确返回 6/37/10，**不验证签名、不发布、不产生 DB Authority**。仅接受 `solution.ecommerce.growth@1.11.0`，原 `publish(bundle_dir, actor)` 仍只接受旧 `1.3.0` 并保留 source revision `1.2.0`。
- 分析模板的 bundleRef 校验可显式按候选版本 exact 匹配；原调用默认旧版本，避免破坏既有发布。Agent/Logic/Capability、兼容 map、schema/policy 的结构和交叉引用沿用正式旧校验。
- 真实当前签名包目录只读检查返回 `(6,37,10)`；此结果只是内容可解析，不是签名/Registry exact 或可运行证明。

## 验证与边界

- `test_aip6_ecommerce_solution_pack.py` 只读/纯校验子集 5/5 通过：当前候选 6/37/10、旧版内容合同、旧版 manifest version drift 拒绝、分析模板漂移拒绝。测试未运行会向 DB 发布的旧用例。本地候选检查未触碰当前新库。
- 浏览器运行页仍显示六角色投影错误及 0 路由/0 供应商；没有 UI 改动或假绿。`git diff --check` 通过；代码变更只限发布器纯解析和对应测试。
- 下一波必须将 Registry/TrustRoot/签名 exact 与当前候选解析组合成正式只读 preflight，并设计单一来源 `1.11.0` 发布及旧 `1.2.0` 安装兼容。未经该前置不调用任何 publisher 写方法。当前库三张定义仍 0，Runtime binding 0。
