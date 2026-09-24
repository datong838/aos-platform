# W5c5i additive Host 租约基础核验（2026-09-25）

上位 W5c5h 排他设计、AR1-c `ar1_003`、231 A0-V/231-9 BG-00；方案 `1166eb17` 先行，实现 `df56d2c1`。生产 Host/worker/Owner 未接入，未运行真实关闭。

## 九步证据

1. 复习 `ar1_003` 目录/OID/assignment、Alembic 原 head=`a0v_092`、隔离 PG 夹具及 W5c5h 的未实现边界。
2. 文件仅本方案、新增 `services/aos-api/alembic/versions/a0v_093_host_lease_foundation.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5i_host_lease_pg.py`、本 verification；Host/worker Python、前端零改。
3. `a0v_093` 仅新增默认空的租约头/不可变事件表及目录角色受限 acquire/renew/release；按 DB 时钟 bounded TTL、单调 epoch、token 哈希、当前 OID/Host/assignment revision 与租户作用域校验。所有直表权限撤销，登录角色需显式 `SET ROLE aos_extension_directory`；任何未知拒绝。真实 `aos_meta_head` 只读读回仍为 `a0v_092` 且新表 `to_regclass=NULL`，**本波未对真实数据库应用迁移**。
4. 隔离 PG 专项 **7 passed**：空默认、唯一持有/并发一胜、续租/释放、过期接管 epoch、旧 token 拒绝、OID/assignment/scope 漂移、超限 TTL、直表读写与事件篡改拒绝。最初测试因 `NOINHERIT` 登录未切换目录角色失败，修正测试会话后通过；未放宽生产权限。
5. 有界累计 W5c3–W5c5i、定义、attempt、lease、preparation、Host/目录 **337 passed、11 skipped、7 warnings、31.63s**；最后新增哈希/直读断言专项复测 7 passed。隔离 `aos-dev-pg` 已停，`git diff --check` 通过。
6. 5174 浏览器只读见 12 单路计划、A0-V 整组 rev4 已停用；`BROWSER_PARTIAL`，页面不证明新迁移或 Host 排他。未保存、运行或冲刷待同步队列，临时页/前端已关闭。
7. 方案/代码一致但阶段性：新表在真实库尚不存在；生产 Host 未持有租约、worker 未同事务 fencing，故不能将租约机制视作已部署安全能力，更不能充当物理第二 Host=0 或旧组关闭授权。原组仍 12 Run running、Receipt 0，严格 24h 未到线，A0-V/BG-00 未过。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5j：Host opt-in acquire/renew/失权停止，默认 off；必须先独立评审和测试，不启用真实 Host。之后逐 worker 同事务 fencing。

m1 单写不 push；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary；商城源行不读。
