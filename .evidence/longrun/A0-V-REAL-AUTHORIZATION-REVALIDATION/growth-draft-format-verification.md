# 增长计划草稿格式检查点

2026-09-11，基线0f588e38，m1串行，无push。按growth-draft-ingestion-plan.md拆分检查点。

- GrowthPlanItem可选EvidenceBundle exact来源，GrowthPlanRevision可选Artifact exact来源。空字段省略，兼容既有计划序列化。
- 新解析器仅接受128KiB以内严格JSON、非空正文、有限数值、1–100条建议、逐项非重复且有界来源索引；拒绝模型自授审批、预算、tenant等额外字段。解析结果不授予任何执行或保存权限。
- Red：新测试因模块尚不存在而失败；Green：新测试+既有authority contracts/store/growth approval，39 passed，exit0。
- 既有7条依赖警告和进程退出JDBC日志流关闭告警仍在，未作无关修改。
- 本次无数据库/Provider副作用，不改变实际服务基线，不声称真实计划已生成。
- 未完成：当前来源/marking/撤销核验、固定prompt绑定、原SUCCEEDED attempt/Artifact核验、Owner原子保存与克隆重放；之后才接实际生成入口和页面、审批来源重验及真实业务首链。
