# W5c4u 失败 attempt 权限与 Host 健康独立诊断方案（2026-09-25）

上位为 231 A0-V→A1、231-9 BG-00→BG-01/02；前置 W5c4r 唯一自然 attempt `PermissionError`、Host `HealthObservationStale`，W5c4s rev4 disabled，W5c4t 正式 stalled 收敛仍待 DB 严格 24h。**本波只读诊断，不重启 Host、不恢复旧代、不调用 closure/retire/run_definition、不读取商城源行。** 两个错误时间邻近，不预设同根因。

## 文件级九步

1. 复习上位及原 Owner：查 W5c4r 的正式状态/Host 栈、`pipeline_snapshot_group_recovery_authority.py` 权限分支、`extension_runtime/verification_commit.py`/`lease_renewal.py` 的健康新鲜度与租约链；核当前租户授权和定义 rev4 不漂移。
2. 文件清单：本方案、只读诊断证据 `w5c4u-permission-host-health-diagnosis-verification-20260925.md`；如需可重复脚本或测试，另列精确路径并先补本方案。默认不改业务代码或生产状态。
3. 最小动作：用现存日志、代码与只读 DB 精确收集异常链、权限现值/历史可得证据、Host 健康探测时序；不得以当前权限等同事故当时权限。记录无法定位的缺口。
4. 专项验证：对提出的每个根因假说给出可证伪的代码分支、时间和只读事实；没有足够证据则保留 UNKNOWN，不写猜测修复。
5. 累计回归：若无代码改动，复核 W5c4t 的 102 passed 基线与只读组资格；若有后续修复，先另波方案及 RED/GREEN 后累计测试。
6. 浏览器验收：仅复核 AOS 计划页当前只读入口；不能展示异常链则明确 BROWSER_PARTIAL，不触发运行。
7. 一致性复审：诊断结论不能改变 W5c4t 的 24h 门、旧 generation 冻结、零业务读写和未完成状态；尤其区分 Runtime Host health failure 与 worker 18181 状态。
8. 证据/上下文：本波 verification 落盘提交；CAS 更新 AOS 项目开发上下文与 Prime 受管独立记忆并读回。
9. 下一波：依据证据选择 W5c4v 最小修复方案，或若严格 24h 与全部新鲜门禁满足，独立启动正式 stalled closure 方案；任何未知提交边界继续冻结。

停止条件：发现第二 attempt、effect/Receipt 增量、定义身份变化、授权不符、日志无法建立精确链或任何必须写入才能“验证”的诉求，停止该路径并记 UNKNOWN，不手工补跑。
