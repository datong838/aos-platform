# D01治理执行服务

2026-09-11，基线021157e8，AOS-000573。沿用D02现有受治理Executor、原文保留和等待后fresh clock模式。

新增 `services/aos-api/aos_api/ecommerce_analyst_portrait_service.py`：类型化完整生成命令（Method/Eval/每MetricQuerySource/cutoff + budget/capacity/attempt/version/classification），内部仅接受保留原文的治理Executor；同scope当前running D01；已存在成功attempt只恢复，其他状态不重发，命令漂移拒绝；完整输入同事务读+不可降级classification+固定prompt，退出事务才派发Executor；等待后取新时钟接Receiver。无公开入口、无自建Provider、无默认放行预算或质量状态。业务宿主真实质量对账未齐备前不安装运行此内部服务。

新增对应单元组合测试：退出事务后调用、原命令deepcopy、慢调用后新时钟、来源拒绝不调用、现有unknown不重试、成功重放不调用、错误skill/version/classification/storage。复用画像inputs/receiver和诊断service回归。下一波D01阶段worker与正式宿主配置接续，首链未完成。
