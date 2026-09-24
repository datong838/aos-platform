# W5c4t 失败组正式收敛资格与权限诊断方案（2026-09-25）

上位方案为 231 的 A0-V→A1 门及 231-9 的 BG-00→BG-01/02；前置 W5c4r `0c9a8c42` 失败、W5c4s `b5570db4` 将定义 rev4 disabled。**本波全程只读，不调用任何 closure、retire、run_definition、Host restart 或商城源行读取。** 原 12 Run 仍 running，不能把停用当退休。

## 文件级九步

1. 复习：对照 `a0v_083_snapshot_unaccepted_group_closure.py` 和 `a0v_091_snapshot_stalled_group_closure.py`、`pipeline_snapshot_stalled_group_closure.py` 与历史 W3/W4 正式关闭脚本。前者要求 group claim/input/member、source claim、ingress command 等均零；后者要求当前定义 disabled、12 Run 从未起 executor 且全体 `started_at < DB clock - 24h`，并保留 effectEvidence 与非业务接受 Receipt。
2. 文件范围：本方案、只读 `scripts/a0v_w5c4t_closure_feasibility.py`、专项 `services/aos-api/tests/extension_runtime/test_a0v_w5c4t_closure_feasibility.py`、本波 verification。无业务库写入与服务重载。
3. 最小实现：纯只读查目标定义 rev4/hash、原 cron claim/唯一失败 attempt、12 Run 完整字段、原 group effect **计数**、现有 closure Receipt/canary、Store/link/projection 总量；用数据库 `clock_timestamp()` 而非本机时钟计算**最晚 Run started_at + 24h**。只给 `UNACCEPTED_PATH_REJECTED_EFFECTS`、`STALLED_WAIT_24H`、`STALLED_ELIGIBLE_REQUIRES_FRESH_AUTHORITY` 或冻结建议，永不自动调用关闭 Owner。
4. 专项测试：覆盖 effect 非零拒绝无效路径、24h 严格不等号、Run/定义/attempt 漂移冻结、eligible 也只建议而不执行。先 RED 后实现。
5. 累计回归：隔离测试库上合并 W5c4r/s/t 与 stalled/unaccepted Owner 合同相关测试；不使用共享库。
6. 浏览器验收：只读复核 AOS 页当前 12 计划与整组入口；不点队列冲刷或运行。若页面仍不能独立证明 rev4 disabled/失败组，标 BROWSER_PARTIAL。
7. 方案/代码一致性：核正式 SQL 与本波计算同一 24h 严格门、group effect 计数无源行、冻结条件覆盖身份与第二 attempt；`PermissionError` 与 Host `HealthObservationStale` 时间相邻只作线索，不推断因果。
8. 证据与记忆：verification 落盘提交后，用 expected revision CAS 更新 AOS项目开发上下文及 Prime 受管长记忆；保护 docs dirty 文件。
9. 下一波 W5c4u：对 `PermissionError` 的原始触发位置和 Host 3 秒健康新鲜度/租约锁等待作只读追踪与最小修复设计；如到 24h 资格仍未到，继续做可独立验收的非业务改进，不提前关闭 Run。资格到时才以新文件级方案、唯一 key、原维护 Owner 正式关闭，随后退休定义。

截至本方案：12 Run 最晚 `started_at=2026-09-24 20:00:04.800482 UTC`；正式 24h 最早边界在 **2026-09-25 20:00:04.800482 UTC 之后**，还需当时重验全量门禁。任何未知结果、额外 attempt、副作用增量或权限漂移先冻结，不改宽 SQL 条件来抢跑。
