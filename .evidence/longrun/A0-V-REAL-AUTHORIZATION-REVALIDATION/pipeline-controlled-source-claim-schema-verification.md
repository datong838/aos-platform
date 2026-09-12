# 受控读取占用存储验证

2026-09-12，m1基线9c87c6c8。新增a0v_024（前序a0v_023）及隔离PG测试。每个现有ScheduleRun只能绑定一个exact Control与actor；同一控制的调用序号唯一且1..32，跨租户/运行/管道/代际/控制版本/hash的绑定被外键拒绝。强制RLS，历史UPDATE/DELETE/TRUNCATE拒绝，显式清理旧默认ACL后runtime仅SELECT INSERT。

先因迁移文件缺失RED，随后专项19项与前序控制schema15项，共34 passed。实际运行AOS_EXTENSION_PG_TEST=1，18432独立测试环境；conftest独立数据库完整upgrade head，专项使用一次性schema。AR2闭包1798/158/93五类错误空；diff check通过。未在真实aos_meta_head部署024，未调用商城源、未启用P01。

此表仅记录占用，不能单独授权读取，也不自动认定源调用已经发生或成功。序号32是合同总边界，具体maxSourceCalls需后续Owner在当前安装锁内检查。既有占用无原批次会明确停在未知状态，不能以修复测试为由重发；恢复续期与旧入口拒绝绕过尚待实现。

下一波：严格占用记录回读及Current Control Owner组合；提交占用后才允许读取，首次及重入严格区分。随后源读取/Ingress同批次保存、每段恢复当前权限重验、正式入口及真实业务验收。局部Schema Lease交付关闭，主A0-V任务继续。m1不push，230 L0挂起。
