# W5CB4 当前签名包 AIP 定义发布可行性 verification（2026-09-27）

## 签名包与内容事实

- 当前发布/批准安装的 growth 包是 `solution.ecommerce.growth@1.11.0`，签名包位于本次新建 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-state/signed-bundles/solution.ecommerce.growth/1.11.0/`；前一轮 Registry/TrustRoot/签名、安装 Receipt 已通过 exact 验证，本波只读文件和库，不重新执行发布。
- 签名包有 6 Agents、37 Logics、10 Capabilities；兼容 map、贡献 schema、运行 policy、分析模板也存在。和旧源码 `bundles/solutions/ecommerce-growth` 对比，Agent/Logic/Capability、兼容 map、schema、policy 六文件逐字节相同；分析模板唯一文本差异是 `bundleRef` 从 `@1.3.0` 指向 `@1.11.0`。
- 新库三张 AIP 全局定义表仍 0、Runtime binding 0；本波没有写库或让跨页投影变绿。

## 阻断及不能做的捷径

- `AipSolutionPackPublisher.publish` 当前仅接收 `1.3.0`，生成的 `sourceRef.revision` 固定 `1.2.0`；`AipEcommerceAgentInstaller._definitions` 也仅筛 `1.2.0`。直接运行旧 CLI 会拒绝当前包；改个常量后运行则既缺当前签名包/Registry exact 验证，又可能让旧环境既有来源不可见，不是安全接续。
- 发布器逐项写 10 Capability、6 Agent、37 Skill，非单事务大命令。未知中途结果必须按每项正式 Owner 的幂等与独立回读对账，不能换键全量重发；当前测试虽有旧版本二次 publish 幂等证明，不覆盖新签名来源。

## 下一波最小设计目标

- 以当前 Registry published `bundleId/version/contentHash`、TrustRoot 签名和本地只读 signed bundle root 的 exact 匹配作为新 CLI 前置；publisher 接受显式经验证 source revision，并保留旧 `1.3.0/1.2.0` 合同。installer 依据当前正式来源选择完整的 6/37/10，不跨版本拼接；当缺失/不完整时继续 fail closed。
- 先改发布器与 installer 的隔离测试，覆盖错签名、错包/版本、部分发布、重复同内容、旧来源兼容及租户边界，再考虑当前新库正式发布。完成前不向当前库填定义、不开 Runtime Host/Provider。
