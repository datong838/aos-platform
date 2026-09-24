# W5c4w 正式 stalled Owner 合同预检核验（2026-09-25）

上位 231 A0-V、231-9 BG-00；计划 `w5c4w-stalled-owner-contract-preflight-plan-20260925.md` 先行提交 `99a08d93`，测试提交 `ca4fe8fc`。本波仅模型/静态 SQL 合同测试，不调用真实或隔离 Owner 关闭事务，更非业务接受。

## 九步记录

1. 复习 `pipeline_snapshot_stalled_group_closure.py` 的 exact request、角色与读回；`a0v_091` 的 admin/owner、rev4 disabled、12 Run/严格 24h、effectEvidence 与 `businessAccepted=false`。
2. 文件范围限本方案、`services/aos-api/tests/extension_runtime/test_a0v_w5c4w_stalled_owner_contract.py` 与本核验；无 Owner/迁移/业务代码修改。
3. 新测试只构造随机 fixture 身份，校验有效请求与非 canonical group、空/多余 ref、错误 reason、非规范 key、额外字段拒绝，并静态核正式 SQL 关键不变量；没有真实组调用。
4. 测试专用波，没有生产实现待 RED；7 项新测试 **GREEN**。其证明范围仅模型和代码文本，不把 fixture 当真实验收。
5. 隔离 `aos-dev-pg` 合并 W5c3/W5c4、定义、attempt/lease/preparation 合同 **184 passed，7 warnings，20.92s**；测试库已停止。W5c4v 的更宽恢复 PG 集合中止事实仍保留，不由此覆盖。
6. 浏览器 5174 `/data/schedules` 只读：12 条单路计划；整组采集页最终载入多项已安装实例选项，但“已保存的配置”仍显示尚无数据组，不能证明后台 rev4/正式资格，`BROWSER_PARTIAL`。未点保存/同步/冲刷，临时页与前端已关闭。
7. 方案一致性：静态合同比实际 DB 事务测试证据低，无法授权真实关闭。实时资格脚本仍 `STALLED_WAIT_24H`、`automaticAction=false`，不改变 W5c4t 的严格边界与旧代冻结。
8. 本 verification 先提交，再 CAS 同步 AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c4x：隔离 PG 上补正式 stalled Owner 的事务级成功/拒绝合同；若严格 24h 和原组全门禁已过，先另起真实关闭方案再唯一调用。定义退休更后一步。

当前定义 rev4 disabled、原 12 Run running；Store/link/pending 本波无副作用，A0-V/BG-00 未过门，230 L0 挂起，m1 不 push。
