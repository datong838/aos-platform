# D01画像固定生成契约

2026-09-11，基线14c2483f，AOS-000573。按231-5画像→评审→诊断顺序，当前仍缺D01实际生成通道；先实现纯请求与原始回答转换，再由宿主Receiver接Owner/L3/治理执行，不绕过来源质量。

新增 `services/aos-api/aos_api/ecommerce_analyst_portrait_generation.py`：完整Method、MetricDefinition、原始QueryRequest/Result、EvalContract、Bundle材料序列化。复用描述方法适用性验证；每项QueryRequest/Result必须完整出现在已给Evidence材料中，严格同scope/cutoff、hash和唯一inventory，固定prompt只允许summary/assumptions/uncertainty/sourceIndices/metricIndices。最多16000字符，不截断。纯函数不声称输入已获正式授权；后续Receiver仍须Owner读取当前权威、真实质量/对账及披露。

修改 `ecommerce_analyst_authority_contracts.py` 的Insight增加可选generationArtifactRef，旧版本序列化省略空字段保持hash兼容。完成生成转换要求原始成功attempt、Provider/usage receipts、同scope/actor、原Artifact正文hash、重建原请求hash；模型只能选给定索引，kind=observation与权威引用由宿主指定，原Artifact随Insight保存。无DB写入/Provider调用/HTTP入口。

新增对应纯测试：完整输入、权限元数据续期不改变prompt、坏hash/来源缺项/重复/过大/未知freshness、失败或漂移生成拒绝、稳定Insight与旧hash兼容。退出后接D01受信Receiver和执行worker，真实首链仍未完成。
