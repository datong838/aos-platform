# W5c5h 跨机器 Runtime Host 排他权威设计与缺口审计（2026-09-25）

## 现有事实与不可越过的差距

- `ar1_003` 的 `extension_runtime_host_assignment` 为每租户唯一受管目标，identity/revision/receipt 保证配置历史，不记录进程心跳、租约持有者或 fencing epoch。`PostgresRuntimeTenantDirectory.read_descriptors()` 读取 assignment，不取得独占锁。
- `scripts/a0v_ecommerce_runtime_host.py` 对三个固定路径持有 `fcntl.flock`，仅能阻止共享相同本机/文件系统锁路径的第二启动器。W5c5c 只数本机已知 Python 命令行；W5c5f 只证目标租户单一受管 assignment 和原代 3 条**资源**租约已释放。资源租约不是 Host 存活租约。
- `pg_stat_activity`、本机 `ps`、状态文件或数据库目录静态行，单独都不能排除另一台机器上有未登记进程，亦不能阻止检查后新启动。W5c5g 因此正确维持 `topologyComplete=false`、`closureAuthorized=false`。
- 当前真实组仍 definition rev4 disabled、12 Run running、stalled Receipt 0；严格 24h 尚未到线。此设计不授权真实关闭，也不修改现有 Host。

## 目标合同（分波实施，**此处尚未实现**）

1. `a0v` 专属的 additive Host 租约表：`(org_id, project_id)` 唯一；记录受管 `host_id`、assignment revision、随机 holder token 的摘要、单调 fencing epoch、DB 时钟 `expires_at` 与不可变 acquire/renew/release 审计。默认空表、旧 Host 继续原行为，迁移本身不激活新权威。
2. 仅受限的目录/维护角色经 SECURITY DEFINER 函数申请/续租/释放；严格校验当前 enabled identity、OID、assigned host/revision、调用数据库角色、DB 时间与 CAS token/epoch。未过期租约不可被第二 Host 抢占；过期接管必须递增 epoch。续租/释放旧 token、角色漂移、assignment 变更一律拒绝。无可重放的原文 token 落库或输出。
3. Host 启动：本机 `flock` 仍保留；读取受管目录后、任何租户 worker materialize/serve 前取得 DB 租约；定期按 DB 时钟续租，失败立即 stop/drain，不在失去权威后发起新工作。Crash/网络分区时，只靠 TTL 不足以 fencing 已启动的外部副作用。
4. 所有会推进租户受管工作状态的 DB Owner/worker 需在**同一事务**校验当前 holder epoch；跨事务“先查租约再写”无效。外部副作用继续依赖正式幂等/Receipt、未知结果冻结，不因 Host 租约而自动重发。迁移期间旧 Host/旧角色必须被显式停机/撤权且完成连接与 worker drain，不能与新合同双跑。
5. 真实 stalled 关闭是独立维护者动作：未来执行方案须在一个 Owner 事务内证明原定义 disabled、12 Run 严格 >24h、零新受管 Host 有效租约及精确业务零副作用，再关闭并独立审计。**这仍不能代替用户原定“第二 Runtime Host=0”物理/全机读回条件**；必须另列受控主机清单与进程/容器读回，不得仅凭 DB 无租约宣称全机 0。

## 分波与验收

- W5c5i：仅 additive 表/SECURITY DEFINER 申请续租释放的隔离 PG 合同；覆盖双申请并发、过期接管 epoch、过期旧 token、role/OID/assignment 漂移与 RLS；生产 Host 不启用。需要先复审 DBA 权限与现有迁移头，避免覆盖其他迁移线。
- W5c5j：Host opt-in、启动前 acquire/周期 renew/失效停止，默认关闭；专项故障注入和旧行为回归。**只有本机 Host opt-in GREEN，不能称全机安全。**
- W5c5k 起：逐一把相关 Owner/worker DB 状态写入同事务 fencing；外部 effect 幂等独立验收。完成全量覆盖及旧角色撤权前，租约只是诊断，不是排他权威。
- 最终执行波：清单化所有受控机器/容器与 DB 连接，确认第二 Host=0；严格 24h、新方案/唯一 key、正式 Owner 单次事务、独立 Receipt/12 Run 审计、定义正式退休、direct successor。任一未知立即冻结。

风险：TTL 与宿主时钟不能混用（以 DB clock 为准）；资源租约与 Host 租约不可混淆；lease GREEN 不等于旧进程被 fencing；无全机资产清单时不能谎称“第二 Host=0”。230 L0、商城源行、dev-org canary、旧 attempt 均保持原边界。
