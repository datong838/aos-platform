# D01原始产物接收与三阶段事务修复

2026-09-11，基线cb0e30a4，AOS-000573。

D01接收器核验成功attempt、D01 Run/route/policy、原文本权限/hash和TaskRun/AgentRun/attempt归属，首次读取统一Owner/L3输入后按正式Owner发布Insight。历史重放返回原结果，检查actor/method/eval/cutoff/原Artifact，不重开源授权，不授予新执行权限。新增历史Insight精确读取和receipt查询。

实PG回滚测试发现原分析Owner._publish主动commit，接收器直接bound原连接导致外层回滚失效。D01/D02/D03统一改为现有TransactionBoundConnectFactory包装Owner；Owner独立调用语义不改，外层唯一提交。D02/D03失败注入迁移到外层事务退出前，验证完整回滚和随后正常并发/重放。该缺陷修复不掩盖旧验证范围不足。

最终84通过、1跳过（旧独立schema测试未启用，已有完整一次性数据库路径覆盖），7既有框架警告，进程退出JDBC日志错误仍存在，退出码0。D01新增24个测试含真实Owner保存/回滚/跨租户，D02/D03完整PG合成图回归。diff检查通过。尚未做D01真实全图Provider执行；新Receiver无公开入口/主库变更，无push。

下一波D01治理执行service与TAOR阶段worker；事实质量、对账、真实源连接及首链仍未完成，不能把内部接收通过当作经营效果或发布授权。
