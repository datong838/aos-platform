# 025主库部署与运行复核

2026-09-13；脚本799f8758；m1独立迁移Lease。

17:31:21Z独立克隆aos_schedule_binding_20260913_ti4_test恢复并升级通过；备份4,915,146 bytes，sha256:34ead45f4af424d4c6240c68979e80e00686daf2885fe4997f4f0ac69b6ce229，受保护保留于.aos-recovery-20260913/state/schedule-control-binding-deployment/aos_meta_head-before-a0v_025.dump。

17:31:45Z主aos_meta_head正常Alembic从024升级025；12张既有关键表前后行数/摘要相同。pipeline_schedule_control_binding为空、强制RLS、两不可变触发器、3 validated FK正确，runtime仅SELECT/INSERT。迁移hash与prepare一致。没有写批准、没有取源或业务写入。

17:32:47Z通过真实aos_a0v_runtime_20260912会话正式采纳aos_runtime角色，主库读关联接口成功；新表SELECT/INSERT=true、UPDATE/DELETE/TRUNCATE=false；原claim和计划/run所需权限均符合。P01对应meta_schedule当前不存在，而不是已有disabled计划；未发现该计划未知停止历史。后续正式创建/绑定/启用仍待做，不能伪造存在。

17:35:11Z当前安装afd792de-e85e-4680-86d0-c83404824fb3 runtime ready/enabled/fence=false/binding@4；3容器running，188续约，elapsed11622.22825秒，canary0。API旧进程仍未重载。只证明包运行连续性，不是经营链连续观察。

下一波先隔离旧Pipeline直接执行入口与受控运行，再正式激活设计、API运行身份配置/重载、真实批准和新P01计划执行。保持原失败/未知结果不重读源，230 L0挂起/no push。备份和克隆保留，不做破坏性降级。
