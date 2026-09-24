# W5c5f Host 目录权威只读门核验（2026-09-25）

上位 231 A0-V/231-9 BG-00；方案 `4a94c77e` 先行，实现及方案措辞校正 `6f04c28a`。无 Host/Owner/迁移改动，无锁抢占、凭据或商城源行读取。

## 九步证据

1. 复习 `ar1_003` 受管 Host identity/assignment/不可变历史、生产 selector、W5c5c 本机已知 launcher 与 `a0v_091` 关闭门。
2. 文件为本方案、新增 `scripts/a0v_w5c5f_host_directory_authority.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_w5c5f_host_directory_authority.py`、本 verification；其他运行代码零改。
3. 一次 repeatable-read/read-only 事务核当前 assignment、identity/角色 OID/成员/非特权属性、各自历史 rev1、原 generation 资源租约状态、原定义 rev4 disabled/hash、12 原 Run running、stalled Receipt 0。真实输出 `MANAGED_HOST_DIRECTORY_READ_ONLY_GREEN_INCOMPLETE_TOPOLOGY`，受管目录目标 Host 为 `a0v-local-ecommerce-host-20260912`，3 条原代租约均 `released + observed_release`。
4. 专项 **17 passed**，覆盖 assignment/revision/OID/成员/历史/租约/定义/Run/Receipt 漂移冻结及只读实现静态边界；真实门 `topologyComplete=false`、`closureAuthorized=false`、`automaticAction=false`。
5. 有界累计 W5c3–W5c5f 与定义、attempt、lease、preparation **236 passed，7 warnings，29.18s**；隔离 `aos-dev-pg` 已停止；`git diff --check` 通过。
6. 5174 浏览器只读见 12 单路计划与 A0-V 整组 rev4 已停用；`BROWSER_PARTIAL`，页面不能证明全机进程/DB 权威，未保存、运行或冲刷待同步队列，临时页/前端已关闭。
7. 方案/代码一致性复审发现 attempt 表没有资源租约 operation_id 外键，已在方案校正为精确 generation 范围，不能声称 operation 级绑定。DB 目录仅证明受管分配及当次快照，不排除非受管进程、另一物理机或后续竞态。真实关闭仍需严格 24h、新方案/唯一 key、同事务 Owner 门、独立审计，A0-V/BG-00 未过。
8. 本 verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5g：继续补全真实关闭前全机/权威门，或处理不依赖真实关闭的安全研发债；到线后另立真实关闭方案，再正式退休/direct successor。

m1 单写不 push；旧 attempt 不补跑；230 L0 挂起；dev-org 零 canary；未知冻结。
