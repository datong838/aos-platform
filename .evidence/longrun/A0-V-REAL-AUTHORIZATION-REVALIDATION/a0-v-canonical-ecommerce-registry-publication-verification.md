# A0-V Canonical 电商 Registry 首次发布验证

## 1. 结果

`A0V_CANONICAL_ECOMMERCE_REGISTRY_PUBLICATION_GREEN`。

隔离恢复库已 canonical publish 四个 v4 精确版本；随后完整重放只读取并核对同一组 published 对象，Registry mutation 四项计数均为 0。此阶段没有创建 Composition、Installation、runtime operation/binding，没有调用 Provider 或外部发布。

## 2. 首次写入

首次执行前，目标版本查询为 0；执行后以下四个版本均为 `published`，content hash 与 v4 build receipt 一致：

| Bundle | Version | content hash |
|---|---|---|
| `domain.ecommerce.core` | 1.1.0 | `sha256:cff310a440dcd75cd70cf8b31a56a237fccb39fabcdecda2b4ae3a1f77f4e4e1` |
| `platform.ecommerce.niushop` | 1.1.0 | `sha256:5a3e65d39ac276d2e9ab761835195fc3f5d9ace9d253b47368c5895c62402cd3` |
| `solution.ecommerce.growth` | 1.4.0 | `sha256:23d432e1b01e5255d9c309a902dec30983366f8c2a6738854822fa5015790042` |
| `solution.ecommerce.operations-base` | 1.2.0 | `sha256:eaf3a9ac9e0faca35246ed85d709ad97c8e1e8a4e5a7e315f1b4a0d6f896a298` |

每个版本均以不同 actor 完成 version create、validate、publish；bundle identity 不存在时先按签名 manifest 建立。已有 draft/validated 只允许在内容精确一致时续跑；已有 published 只允许 exact readback。

首次原始回执 SHA-256 为 `382e4981dd824b98971be0e893ae48eb876e68bcf07dcaddf7a62b7a90bca0d8`。该回执的顶层 `effects=0` 来自 Candidate build 输入，不能表示首次 Registry 无写入；执行后已在 `381b48df` 修正字段语义。首次写入可由同一回执中的“执行前 targetVersions 为空”和“执行后 published 四项”对账确认。

## 3. 重放与当前边界

修正后的重放回执 SHA-256 为 `31c2b791f20e4746e20c75ec2b93e9953bf50794fad76dc33c803f45469e0269`。重放前四个目标版本已全部存在；`bundleCreateCount/versionCreateCount/validateCount/publishCount` 均为 0，输出仍是同一组版本和摘要。

首装专项与 Registry/ReleasePolicy 专项合计 `95 passed`；字段语义修正后首装专项 `7 passed`。七条既有依赖 warning 和退出日志告警不影响结论。

## 4. 下一步

下一阶段创建无 baseline Composition lock 和 maker/checker Installation。请求只显式选择 niushop 1.1.0、growth 1.4.0、operations-base 1.2.0，resolver 必须唯一补入 core 1.1.0；解析节点、依赖边、八模块贡献和四个 content hash 任一漂移都阻断。
