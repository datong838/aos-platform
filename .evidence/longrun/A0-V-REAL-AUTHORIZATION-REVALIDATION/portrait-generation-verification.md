# D01固定生成契约验证

2026-09-11；基线14c2483f；AOS-000573；m1单写者。

完成纯固定prompt与原始成功回答转换，完整Method/Metric/Query/Eval/Bundle输入不截断，唯一完整Query来源绑定，模型索引不得脱离原给定范围，所选指标必须保留支持来源。检查原attempt/Artifact正文/request hash/Provider和usage receipts/actor/scope，生成稳定observation Insight和原Artifact引用。完成时间不得早于输入。旧Insight序列化省略空generationArtifactRef保持旧hash。

新增17项纯测试通过，相关画像方法/权威契约/诊断生成/解析回归合计116个不同测试通过（114+新增2）。git diff --check通过。既有7框架警告与退出JDBC日志关闭错误，退出码0。

边界：纯转换不证明当前Owner、披露、质量、对账或Provider权限，不执行模型、不写主库、不等同真实首链。原文授权元数据不进入模型请求，续期不改变请求hash。下一波D01受信Receiver重新读取当前权威和来源，接原始文本Owner、幂等保存与治理执行；源连接恢复仍独立等待。
