# AR1-c 代次在途账本与排空权威检查点

- 日期：2026-09-06
- 基线：e3dc9f7a
- 业务场景计数：0
- 页面变化：无；浏览器验收不适用

## 已实现

新增 `ar1_004` 持久 attempt head 与 append-only event。数据库守卫冻结身份字段，强制 revision 单调和合法状态迁移，并校验事件与 authority head 一致。迁移与 Store 只接纳 `signed_read`；同一规范幂等键由事务 advisory lock 串行化，只有首次持久受理返回一次执行资格，重放永不重新授权执行。

`GenerationDrainReader` 只在 binding 已提交精确 fence 且 epoch 相符时读取。旧代任何 running attempt 都阻止排空；已知终态全部收敛后才返回 true。owner 进程消失时，其他受信进程只能在租约到期后把只读 attempt 推进 abandoned，不能重放外部读取。

## 验证

- 隔离 PostgreSQL 专项：9 passed。
- 扩展运行域累计：723 passed、28 skipped。
- 双连接同幂等键：仅一个 `execute_once=true`。
- 非特权 runtime role：正租户可见，负租户不可见且不可写。
- 原 owner 连接退出：租期前 drain=false，租期后另一连接回收，随后 drain=true。
- 身份字段篡改、事件伪造、错 token、错 revision、未 fence 与 fence 后新 begin 均拒绝。
- Alembic 单 head `ar1_004`、编译及差异检查通过。
- 独立 Prime 第二轮复审 PASS。

## 精确边界与下一交付

本检查点只标记 `GENERATION_ATTEMPT_AND_DRAIN_AUTHORITY_GREEN`。生产 selector、worker factory、短事务提交后外部读取接线、startup 后台生命周期尚未闭合；没有运行共享迁移、真实租户 assignment、OCI、Provider、预算扣费、业务任务派发或发布动作。

下一交付把真实 drain、可信目录、三平面身份预检、当前配置／权限 reader 和具体 consumers 组合成 production selector/factory；任何依赖缺失必须零访问 INACTIVE，完成进程重建联合反证后才接 main startup。
