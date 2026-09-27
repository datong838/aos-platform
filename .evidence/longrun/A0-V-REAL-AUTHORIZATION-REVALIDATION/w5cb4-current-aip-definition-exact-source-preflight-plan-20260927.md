# W5CB4 当前 AIP 定义 exact 签名来源只读前置波（2026-09-27，编码前）

## 上位与现状

- 当前 signed growth `1.11.0` 的内容解析 6/37/10 已由 `8d456476` 证明；AIP 全局定义仍 0。231 BG-00/03 与签名/租户/单写者要求禁止从未经验证的任意目录发布。旧 publisher 写路径不变。
- 本波只构建一个**只读** exact 前置：当前 RegistrySnapshotReader 在一个只读事务中验证 published release/当前 TrustRoot；ManifestLoader 对 allowlisted signed root 重新验证文件哈希和 Ed25519；两者身份、contentHash、signature fingerprint 与当前候选版本必须相等，之后才调用只读 6/37/10 parser。任何漂移 fail closed。

## 文件级

1. 新增 `services/aos-api/aos_api/aip_solution_pack_signed_preflight.py`：依赖注入 snapshot/loader，固定 `solution.ecommerce.growth@1.11.0` 及 sourceRef，精确比较 Registry candidate 与 LoadedBundle；返回只读 proof，不发布。
2. 新增 `services/aos-api/tests/aip/test_aip_solution_pack_signed_preflight.py`：构造真实合同对象/窄 fake，覆盖正确、错哈希、错指纹、缺签名证据、错版本/错来源、parser 内容漂移；断言没有写接口调用。
3. 新增 `scripts/a0v_current_aip_definition_preflight.py`：先复用现有预览 preflight 的精确目标库/签名 Receipt 门，再以只读 RegistrySnapshotReader 与 ManifestLoader 调用上述检查；只输出非秘密证明，不接 `--publish`。在当前新库实测。专项+相邻累计、浏览器仍禁入、方案/代码一致性、verification→m1 提交。下一波才允许设计正式定义发布命令。

## 停止条件

- 签名/TrustRoot/Registry 任何一项未知立即失败，不运行 publisher、SQL 手填、Runtime/Provider/商城源或原 Run。
