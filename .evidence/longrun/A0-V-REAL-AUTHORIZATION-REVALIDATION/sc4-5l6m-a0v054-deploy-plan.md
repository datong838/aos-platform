# a0v054 主库部署方案

Rules：m1 单人串行，先方案后编码，不 push、230 L0 挂起、不改变 E 安装状态。任务 SC4-5L6M-EVENT-DISPATCH-DEPLOY-20260916。

新增 scripts/a0v_event_dispatch_deploy.py，沿用已验证 UI-read 部署器的备份/恢复/校验/不可覆盖意图/读回顺序，保持历史部署器不变。固定源 a0v053、目标 a0v054、主库 aos_meta_head、隔离恢复库 aos_event_dispatch_20260916_test、状态目录 .aos-recovery-20260916/state/event-dispatch-deployment。仅执行一条迁移，检查当前 HEAD 和任务 lease；迁移文件与执行器哈希必须匹配恢复证据。prepare 先保存 pg_dump 并恢复到新库；全部既有 public 普通表按行内容计算指纹（排除 alembic_version），确认升级前后未变。新收据表空、强制 RLS、运行时只读、维护者可插入不可改删、函数仅维护者可执行。

apply 前校验备份权限/大小/哈希、隔离库状态、主库原指纹，固定迁移 advisory lock、有限锁等待与语句超时；记录不可覆盖 apply-intent 后升级。结果未知只 readback。downgrade 被迁移禁止，失败保留数据库备份及隔离库证据，不自动回滚已有业务数据。

新增 tests/extension_runtime/test_event_dispatch_deploy.py 覆盖错误源/目标、证据漂移、状态目录、租约与受保护输出；实际恢复验证作为部署验收。全表指纹只输出计数/摘要，不打印业务行或凭证。成功后再进入独立 E→F 波次。

## 在线基线变化后的确定性接续

第一次隔离恢复验证成功（540 表相同），apply 在创建意图之前拒绝：主库仍 a0v053，但 runtime event/outbox/operation/resource lease 四表被运行中的 Host 更新。保留第一次备份和隔离库，不删除或覆盖。固定第二次状态目录 event-dispatch-deployment-quiesced、隔离库 aos_event_dispatch_quiesced_20260916_test；先记录 Host 启动参数，对唯一受控 Host 发 SIGTERM 并等待其正常停止，主 API 保持服务；在稳定基线重新备份/恢复/迁移，随后按原参数恢复 Host。若仍有变化则定位实际写者，不忽略任意表。停止仅是本地维护窗口，不替代安装禁用授权或卸载 Receipt。
