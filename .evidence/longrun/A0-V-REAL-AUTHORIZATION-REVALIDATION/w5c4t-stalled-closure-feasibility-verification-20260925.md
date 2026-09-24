# W5c4t 失败组正式收敛资格只读核验（2026-09-25）

上位合同：231 A0-V→A1、231-9 BG-00→BG-01/02；本波方案 `w5c4t-stalled-closure-feasibility-plan-20260925.md`，方案提交 `d2cdcf39`。实现及测试提交 `7fd2eadb`。本文件仅证明只读资格判定，不是正式关闭或 A0-V GREEN。

## 九步实录

1. 复习上位方案和正式 Owner：`a0v_083` 未接受路径需要零 group effects，现有 group claim/input/member、source claim、ingress command 非零，故不可走；`a0v_091` 要求 12 Run 从未起 executor、schedule/definition disabled，且各 `started_at < clock_timestamp()-interval '24 hours'`。
2. 文件清单限方案、只读 `scripts/a0v_w5c4t_closure_feasibility.py`、专项 `services/aos-api/tests/extension_runtime/test_a0v_w5c4t_closure_feasibility.py` 和本核验；无生产代码或数据写入。
3. 最小实现以只读事务查精确身份、唯一 claim/attempt、12 Run、effects 和独立总量；纯函数按数据库时钟给出 `STALLED_WAIT_24H` 或仅建议 fresh authority 的资格结果，`automaticAction=false`。无 closure/retire/run_definition/Host restart。
4. 专项测试覆盖非零 effects、24h 等号仍等待、过界只建议、第二 attempt/效果/定义/Run 漂移冻结；连同 W5c4r/s 关键测试 **27 passed**。
5. 隔离 `aos-dev-pg` 累计 W5c3/W5c4 与定义/未接受 Owner 合同 **102 passed，7 warnings**；测试库已停止，不使用共享库。
6. 浏览器 5174 `/data/schedules` 只读验收：单路计划表可见 12 条；整组采集页提示“尚无数据组配置”，已安装实例下拉无对象，不能独立证实 rev4 disabled/失败组。`BROWSER_PARTIAL`；未点保存、立即同步或队列冲刷。临时前端及 tab 已关闭。
7. 对照 `a0v_091` SQL 的严格 `< clock_timestamp()-24 hours`：最晚 `started_at=2026-09-24 20:00:04.800482 UTC`，只在 **2026-09-25 20:00:04.800482 UTC 之后**才可能合格，届时仍需新鲜全门禁。PermissionError 与 Host HealthObservationStale 同时邻近，不推断因果。
8. 本文件先落盘提交，再同步 AOS 项目开发上下文及 Prime 受管记忆；memory-sync 与读回另见 docs 提交。
9. 下一波 W5c4u：只读追踪 PermissionError 精确触发点与 Host 健康新鲜度/租约链，先文件级方案再实现最小修复。未满 24h 不提前关闭；资格到时再走独立方案与正式 Owner。

## 实时只读判定

DB clock 约 `2026-09-24 20:41:42 UTC`，结果 `STALLED_WAIT_24H`、`UNACCEPTED_PATH_REJECTED_EFFECTS`、`automaticAction=false`。定义 rev4 disabled、hash `sha256:d3c28bf5ea17e299fe598b662da238aeecbb3f0f4227c96da3b44a8f4f49c32d`；唯一失败 attempt `a5e60b0d-2d97-44d0-88bf-9f08990624d1`；12 Run 仍 running。group effects：1/1/12/12/12/0/0；Store Receipt 26 无本波增量，live link0、pending0、dev-org canary0、正式 closure receipt0。

结论：本波只读资格核验完成，原 Run 与定义退休未完成，A0-V/BG-00 仍未通过。不可在旧 generation 重发或手工运行。
