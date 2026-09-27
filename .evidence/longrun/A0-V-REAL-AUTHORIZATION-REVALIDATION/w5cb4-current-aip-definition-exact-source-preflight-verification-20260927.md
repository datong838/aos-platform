# W5CB4 当前 AIP 定义 exact 签名来源只读前置 verification（2026-09-27）

## 结果

- `a0v_current_aip_definition_preflight.py` 先复用现有安全预览前置，精确限定 `aos_current_preview_20260927@a0v_106`、唯一 approved 安装、Runtime binding 0、四 published 包、签名树 Receipt。之后 `RegistrySnapshotReader` 以当前 TrustRoot 只读验证发布候选，`ManifestLoader` 对同一 signed root 两次核签；身份、contentHash、signature fingerprint exact 一致，再只读解析 6/37/10。
- 当前实测输出 `CURRENT_AIP_DEFINITION_SOURCE_EXACT_READ_ONLY`：sourceRef `bundle://a0v-current/solution.ecommerce.growth/1.11.0`，contentHash `sha256:3d8817e01f53690adbd58698951c226e8c3917304a9ec4d7eee37d64bf02b328`，signature fingerprint `sha256:b77d7b1b621f68859bee9a51ae95b76a343ddb4ae32d98b4d1fe132425a0bfca`，snapshotHash `sha256:dfc18926a512c9b1c7610d2e61b1312f73b7911e72cb407be0d5d0d3cc2988f3`，6/37/10，writes=0。
- 独立只读 SQL 复查当前库 `aip_agent_template_revision=0`、`aip_skill_template_revision=0`、`aip_capability_revision=0`、`extension_runtime_binding=0`；因此“来源可核”不等于“定义已发布”或“六角色可运行”。浏览器跨页投影继续如实禁入。

## 验证/复审

- 前置专项 + 旧版候选校验 12/12 通过，覆盖错哈希、错指纹、缺/失效签名证据、错来源/版本、二次加载漂移，以及旧 1.3 内容合同。`git diff --check` 通过。
- 本波只读模块和脚本没有 `publish`、`INSERT`、Runtime/Provider 调用。TrustRoot/Registry/目录不同步时 fail closed；这个 proof 是时点证明，后续写入边界必须重新执行前置并在部分发布后按 Owner 逐项只读对账，不能长期复用旧证明。

## 下一波

- 按用户要求先整理 231 总控下过去、当前、未来的唯一波次索引和当前所处位置；不把所有 evidence 文件逐个当新业务里程碑、也不凭提交数计算百分比。
- 然后设计当前 signed 1.11 source revision 的正式 6/37/10 发布、旧来源兼容与部分提交恢复；未完成前当前库仍 0、Runtime Host/自然 worker 关闭。
