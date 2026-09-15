# a0v054 主库部署方案

Rules：m1 单人串行，先方案后编码，不 push、230 L0 挂起、不改变 E 安装状态。任务 SC4-5L6M-EVENT-DISPATCH-DEPLOY-20260916。

新增 scripts/a0v_event_dispatch_deploy.py，沿用已验证 UI-read 部署器的备份/恢复/校验/不可覆盖意图/读回顺序，保持历史部署器不变。固定源 a0v053、目标 a0v054、主库 aos_meta_head、隔离恢复库 aos_event_dispatch_20260916_test、状态目录 .aos-recovery-20260916/state/event-dispatch-deployment。仅执行一条迁移，检查当前 HEAD 和任务 lease；迁移文件与执行器哈希必须匹配恢复证据。prepare 先保存 pg_dump 并恢复到新库；全部既有 public 普通表按行内容计算指纹（排除 alembic_version），确认升级前后未变。新收据表空、强制 RLS、运行时只读、维护者可插入不可改删、函数仅维护者可执行。

apply 前校验备份权限/大小/哈希、隔离库状态、主库原指纹，固定迁移 advisory lock、有限锁等待与语句超时；记录不可覆盖 apply-intent 后升级。结果未知只 readback。downgrade 被迁移禁止，失败保留数据库备份及隔离库证据，不自动回滚已有业务数据。

新增 tests/extension_runtime/test_event_dispatch_deploy.py 覆盖错误源/目标、证据漂移、状态目录、租约与受保护输出；实际恢复验证作为部署验收。全表指纹只输出计数/摘要，不打印业务行或凭证。成功后再进入独立 E→F 波次。
