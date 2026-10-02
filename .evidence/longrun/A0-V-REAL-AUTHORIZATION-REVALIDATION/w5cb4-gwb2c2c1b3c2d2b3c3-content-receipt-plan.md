# GW-b-2c2c1b3c2d2b3c3 生成回执来源歧视方案

上位：231-5 §9 的两来源兼容合同；D-waves BG00gw 清单 d2d2 双消费者。当前正式实例因外部 OIDC、八配置、Host 身份和签名来源缺失仍禁入。本波仅在包内解析既有受限生成回执，不执行当前业务或解除 Host。

## 文件级改动

1. `services/aos-api/tests/extension_runtime/test_ecommerce_content_capability_budget_runtime.py`：先 RED，证明单原 `Artifact` 的 `accepted-stage-v1` 回执在未完成、完成态都按同一来源读取；无来源种类、混入四 `ArtifactRevision`、回执与请求来源不一致均拒绝；旧四来源仍通过；调用 `execute_content_capability` 仍在 port 前失败。
2. `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_artifact_review.py`：`ReadableContentArtifact` 对新来源要求显式 `sourceKind` 和单原 `Artifact`；旧字段集、四个 `ArtifactRevision` 校验不变。内容审核请求、Host 不在本波开放。
3. `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/content_capability_runtime.py`：生成回执仅按已验证请求的 `source_kind` 选择来源引用类型和数量；完成态的可读产物要求同一来源种类。请求门禁仍先于 port；不产生 Provider 调用。

## 验收与风险

运行专项和相邻合同测试、语法检查、diff 检查；对照旧分支字节形状及新分支的 requestHash、exact refs。此包内解析器不证明宿主已能生产该回执；生成 Host、人工评审消费者和正式实例仍失败封闭。不得把隔离测试解读为首链。
