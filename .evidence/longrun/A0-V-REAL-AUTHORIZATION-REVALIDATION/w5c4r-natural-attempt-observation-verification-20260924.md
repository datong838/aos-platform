# W5c4r 自然 attempt 观察验证（2026-09-24）

结论：**自然调度真实发生；恢复失败，观察链冻结；不得记 A0-V/BG-00 GREEN。** 本波方案见 `w5c4r-natural-attempt-observation-plan-20260924.md`，等待期修订与非终态记录见同名前缀 `partial-verification`。未调用 `run_definition`、未人工重发、未读取商城源行、未推送。

## 九步复核

1. 上位方案：复核 231 的 A0-V→A1 门与 231-9 的 BG-00→BG-01/02 顺序；当前不能跨入 A1。
2. 文件级范围：仅本波方案、只读观察器、离线预审、两者专项测试与本验证；运行中的业务代码/定义/Host 未在观察时修改。
3. 最小实现与自然结果：定义 `38c5d08c-ee40-4167-b129-8f95276e0c7a` rev3 enabled，hash `sha256:d80287ce2e70e034060c6e056f8e93f3d8c9654b4beccd3bc386e095eda15227`。官方 20:00 UTC slot 在 20:00:04.803356 UTC 自然产生唯一 cron claim，group `081cd331-cdf8-5bdc-891e-e3b82baa77c7`、12 Run。20:04:16.202662 UTC 唯一 `recoverable_store` attempt `a5e60b0d-2d97-44d0-88bf-9f08990624d1` 被接受；20:06:20.003281 UTC 原 Owner 正式记 `failed` rev6、`RECOVERABLE_EXECUTION_EXCEPTION / PermissionError`。这**不是** `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED`，不进入 1800 秒同 attempt 延续分支。
4. 专项：等待期观察器与离线预审合计 15 passed；终态后对 803 条 0600 私有样本运行离线预审得到 `FROZEN_ASSESSMENT_BOUNDARY / SAMPLE_AUTHORITY_OR_OBSERVATION_DIFFERS`，符合最后一条 `FROZEN_OBSERVER_ERROR / ValueError` 的预期，绝非成功候选。独立数据库只读回读确认目标 generation 仅一 attempt、12 Run 仍 `running`/`executor_stopped=false`/`finished_at=null`；Store Receipt 总数仍为启用前基线 26（本次增量 0）、live `ecom_link=0`、projection pending=0、`dev-org/dev-project` canary=0；目标 group 的 recovery/stalled/unaccepted closure Receipt 均 0。
5. 累计回归：测试专用 `aos-dev-pg` 原先于 17:26 UTC 以 exit 0 停止，首次 59 项均在 5433 初始化阶段报错；正式终态后仅重启该隔离容器，执行 `PYTHONPATH=scripts services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_a0v_w5c3*.py services/aos-api/tests/extension_runtime/test_a0v_w5c4r*.py`，结果 **59 passed、7 warnings**。未使用共享测试库。测试后将隔离容器恢复为 stopped；`git diff --check` 通过。
6. 浏览器验收：原以为的 5173 实为另一个项目的 MediaCrawler，识别后立即关闭，未操作。用 AOS 本仓 `apps/web` 在 5174 临时只读启动，页面确认为 AOS、org-org/dev-project、12 条单路计划可见；“整组采集”显示“尚无数据组配置”与无已安装实例，并显示待同步写操作 1。未冲刷队列、未点击运行/保存、未读取源行。浏览器仅为 **BROWSER_PARTIAL / 业务结果未验证**，不能替代独立 DB；已关闭临时前端。
7. 方案/代码一致性：803 条原观察样本从 08:51 UTC 连续到 20:06:59 UTC；20:06:09 最后一条完整样本仍为唯一 running attempt，20:06:59 因原 Host PID17302 消失，观察器按计划写 `FROZEN_OBSERVER_ERROR` 并收笔。Host 日志在 20:06:20 后报告 `RUNTIME_HOST_STOPPED`，根错误 `HealthObservationStale`（lease renewal/verification health），与原 Host 进程不在的只读检查一致；worker PID37241 仍为唯一 18181 listener、IDLE。离线预审拒绝中断样本，独立 DB 确认正式失败，未以配置 GREEN、HTTP 或 worker IDLE 冒充业务成功。`PermissionError` 的精确抛出点尚未被当前日志定位，列为下一波诊断，不推测成 ingress deadline。
8. 证据与记忆：本文件与原 0600 私有 JSONL、冻结 intent/result、Host stdout、独立 DB 查询构成本波证据。先提交本仓；随后按 expected revision CAS 更新 `docs/palantier/AOS项目开发上下文` 并确定性同步 Prime 三条受管长记忆，保护 docs 中其他未提交变更；任何同步冲突另记，不改写本失败事实。
9. 下一波：W5c4s 先只读核冻结后的 definition/head、唯一 claim/attempt、12 Run、零增量与 Host/worker；在文件级方案中明确正式退休当前 enabled 定义的控制路径和 `PermissionError`/`HealthObservationStale` 诊断边界，再经正式 direct successor 重新授权。旧 generation 不重发；230 L0 挂起、m1 单写不 push、`dev-org` 零 canary 均保持。

## 正式边界

本波只封存失败与冻结事实，**不**授权继续使用 rev3 enabled 定义自动再跑下一日，也**不**授权在原 generation 内人工补跑。下一波需先正式关闭未来调度资格并独立回读，再做最小缺陷修复/继任方案。若任何独立结果再变化，先冻结、只读对账，不覆盖本记录。
