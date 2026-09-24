# W5c4r 自然 attempt 50 秒只读观察方案（2026-09-24）

W5c4q `4ad6643f` 定义 rev3 enabled、12 schedule on，下一官方时区 slot 是 2026-09-24 20:00 UTC。唯一 18181 worker PID37241、Host PID17302。**不手工 `run_definition`，不读取商城源行。**

1. 立即启动单一只读观察循环，固定 50 秒间隔：官方 definition/worker/Host/三 held、九路与 claim gate、目标定义 group claim/12 Run、第三继任者 attempt 的 ID/state/revision/错误分类、Store Receipt/projection/canary，以及预算/控制剩余期。私有 0600 逐次落非源行观测；任何身份漂移、第二 worker/attempt、未知提交边界立即冻结，并停止宣称自然成功。
2. 20:00 UTC 前仅显示等待与健康，不触发业务；到点后同一轮持续采样到**唯一 attempt 的正式终态**，然后核 12 Run、Store/投影、Release/Receipt 等正式结果。只认原 Owner 状态及独立 DB 回读，不能凭 HTTP 200 或 worker `IDLE` 判成功。
3. 若出现 `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED` 且十二 Run 仍 running、Store Receipt/ecom_link/projection pending 全0，则走既定 1800 秒有界 saved-snapshot 路径；任何失败/unknown 不手工重发，在本波 verification 中冻结边界，再正式退休/direct successor。
4. 观察终态、verification/commit 后自动进入下一波。观察进程本身不授权副作用；失去观察进程不改变已有定义的自然控制，恢复时先只读按原 group/attempt 认领，不发第二次请求。

## 08:57 UTC 观察器预防性修订（业务未到点）

`W5c4q._worker()` 专用于启用前门禁，要求状态恰为 `IDLE`；自然执行时 worker 会合法进入 `RUNNING`，不能复用它作为 W5c4r 健康判据。W5c4r 应自行只读允许 `IDLE/RUNNING`，仍要求唯一 PID、alive、independent、无本进程 Host、无 error、status 新鲜；`STOPPING/STOPPED` 或异常需以 `FROZEN_OBSERVER_ERROR` 私有落盘并退出，不让进程无痕崩溃。修正后在尚无 claim/attempt 时重新采样验证，再继续唯一观察循环；不得启动第二观察器与正式业务请求。

## 09:07 UTC 无 attempt 有界观察补充

使用已冻结的启用意图 `nextSlotUtc` 作为唯一时钟锚点。若 slot 后 30 分钟仍无本 generation 的 attempt，即使有 group claim 也以 `FROZEN_NO_ATTEMPT_AFTER_SLOT` 停止观察，不推断业务成功、不补发、不手工触发；先独立只读对账 claim/Run/worker/Receipt，再按正式退休与 direct successor 路径处理。只要已出现唯一 attempt，仍按原规则观察至正式终态。该边界是 fail-closed 上限，不改变自然触发和运行时控制。

## 等待期可并行完成的本波离线终态预审

不改、不重启正在运行的 18181 worker、Runtime Host 和 W5c4r 观察器。新增 `scripts/a0v_w5c4r_terminal_assessment.py`，只读取本波私有 0600 采样 JSONL 与 W5c4q 冻结 intent/result；绝不连接商城源、发 HTTP、调用 `run_definition` 或写业务库。精确核一个启用前 baseline、一个最新正式终态、同一 rev3 定义、cron slot、唯一 group/attempt、12 Run 与 Store/link/projection 的**增量**；缺字段、身份不符或未知副作用一律 `FROZEN_ASSESSMENT_BOUNDARY`。成功只输出 `SUCCEEDED_REQUIRES_INDEPENDENT_AUDIT`，deadline 且 12 Run running/零增量只输出 `FAILED_PRESTORE_CANDIDATE_REQUIRES_INDEPENDENT_AUDIT`；二者均不授权自动恢复或宣告 GREEN。专项测试覆盖两条候选路径、非 cron/第二 attempt/Store 增量拒绝。正式终态后还必须独立 DB 回读并落最终 verification，才能收口。修改范围仅新脚本及 `services/aos-api/tests/extension_runtime/test_a0v_w5c4r_terminal_assessment.py`；回滚为不调用该离线预审，不触碰运行态。

## 等待期离线预审连续性补强

首尾对比不足以排除中途曾冻结、身份漂移、额外 claim/attempt 后又消失的情况。预审须顺序核对**全部**私有采样：时间严格递增、观察状态在末条正式终态前始终为等待、定义/worker/Host/九路/门禁/十二 schedule/canary/held 稳定、claim 与 attempt 数量不超过一且一旦出现其 ID 不再变更或消失。任一缺字段或中途异常均只输出 `FROZEN_ASSESSMENT_BOUNDARY`，不提供成功或预存储失败候选。专项测试先复现中途冻结和 ID 更替，再做最小实现；CLI 仍为纯离线建议，不替代独立数据库验收。仅修改同一离线脚本和专项测试，不改变观察器或业务运行态。

## 无人值守九步收口补充（用户 2026-09-25 01:30 CST 追加）

每波按「复习上位方案→当前波文件级清单→最小改动→专项测试→累计回归→浏览器验收→方案/代码一致性复审→证据与上下文/Prime 独立长记忆更新→明确下一波并自动进入」报第 x/9 步。本波已经完成前四步中的等待期离线部分，但第 3/4 步的真实自然执行及最终断言仍待正式终态；不得把局部完成写成整波完成。

1. 上位方案：复核 `docs/palantier/20_tech/电商平台接入/231-工作台业务闭环长程开发路径与波次实施计划.md` 的 A0-V→A1 门、`231-9-栖月汇双侧增长技术合同与原计划增量清单.md` 的 BG-00→BG-01/02 顺序及本波冻结 intent。历史上下文或 D-waves 线索不得取代现行 m1/DB。
2. 文件级范围：本波只改本方案、`scripts/a0v_w5c4r_observe_natural_attempt.py`、`scripts/a0v_w5c4r_terminal_assessment.py`、两者专项测试及本波 verification；终态后所需只读验收记录另行落盘。运行中的 18181/8080/Host 不重载，商城源行不读取。
3. 最小改动：已完成的离线预审仅供终态分类；真实自然 claim/attempt 由现有 worker 唯一产生。未知边界冻结，不手工 `run_definition`，不重发。
4. 专项测试：观察器及离线预审专项必须继续通过；终态样本须用预审及独立 DB 回读验证 exact group/attempt/十二 Run/Store-link-projection 增量与 canary。
5. 累计回归：仅运行本波及前置 W5c4p/q 的相关非破坏性测试，记录命令、通过/失败及未覆盖项；不得用测试代替真自然结果。
6. 浏览器验收：正式终态和独立对账后，优先使用 Codex 内置浏览器只读查看当前安装/调度/运行结果与错误；不登录未知账号、不读取商城源行、不触发运行或发布。若无法取得有效授权页面，明确记 `BROWSER_UNVERIFIED`，不伪造 GREEN。
7. 一致性复审：逐项比对 rev3/hash、冻结 intent、采样、独立 DB、代码判据及上位方案；任何不一致先冻结，不用陈旧 D-waves 或旧上下文覆盖现证。
8. 证据/记忆：最终 verification 先落本仓库并提交；再用 `scripts/memory/memory-status` 核 `AOS项目开发上下文` 旧 authority 与现态差异，按 expected revision 的 `authority-update`/`memory-sync --apply --prime` 确定性更新并回读。`docs` 仓库已有大量未提交改动，须逐目标检查和精确暂存，保护其他文件；Prime 三条受管投影不得模型自由改写。若 CAS/并发冲突，记录阻断，绝不强盖。
9. 下一波：在本波最终 verification 与必要上下文回读完成后，依据成功/失败/冻结的**实际**终态写下一波文件级方案并自动推进；成功才进入 A0-V 后续/BG-01/02，失败走正式退休/direct successor，未知先只读对账。下一波仍保留 m1 单写者、不 push、230 L0 挂起、dev-org 零 canary。
