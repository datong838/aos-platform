# BF 保存快照恢复、1800 秒预算与第二 attempt 冻结验证

## 配置与 authority 转移

- definition rev97 disabled、BF attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev97 disabled 生成 BF rev98 disabled，hash
  `sha256:6dee0bf21e5a0fdc7b0df015c64ce9a7f8d8bc048d9f7722ab324450610dc99c`。
- renew 从 recovery rev31 生成 rev32，hash
  `sha256:aa3cab515d6256eefef3866053301fab2571f0c13aec446f700a26bcdd47fd9b`；同一事务生成
  definition rev99 enabled，hash
  `sha256:055f6d5f65be0b110c9cb980e3125289c01986e6c676665178818f842b2837c3`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与两次终态

- 创建 exact `A0V-BF-SNAPSHOT-WORKER-20260920` deployment lease 后启动唯一自然 snapshot worker PID 75420；
  读回 worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 首个自然 attempt `0a79f73d-7243-4778-90af-2e2109115e73` 使用幂等键尾号 `:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租至 revision 60；
  只读 monitor 以数据库 `accepted_at` 为起点，在 elapsed=1800 秒命中预算。
- monitor 仅输出 `stopWorker=true`，没有进程内联动停止能力；本次 heartbeat 在预算事件之后才重新进入执行，
  worker 在首个 attempt 正式终结与停止信号之间自然领取第二 attempt
  `b61340d4-391f-415d-ac77-65ed8f72321d`（幂等键尾号 `:2`）。这触发计划的第二 attempt 停止条件。
- 停止命令发出后 worker 完整排空并自然退出，无需 KILL；状态为 STOPPED/taskAlive=false，18181 无监听，未产生
  第三 attempt。首个 attempt revision61 为
  `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`；第二个 revision10 为
  `failed / RECOVERABLE_INGRESS_CANCELLED / IngressJournalConflict`。

## 冻结边界

- snapshot worker 已停止，唯一外部 Runtime Host PID 29815 保持运行；临时 worker lease 已移除。
- definition 暂保持 rev99 enabled，但没有 snapshot worker。本波不执行 `pause-terminal`：共享 exact guard 要求
  attemptCount=1，实际 attemptCount=2，因此 fail closed 返回 `SAFE_BLOCKED_MULTIPLE_ATTEMPTS`。
- 本波没有商城源读取、没有手工重发、没有切换 request hash、没有 push，230 L0 继续挂起。下一波只能以 exact
  两次 terminal history 为 authority，先专项结算并将 definition 推进为 rev100 disabled；禁止重启 worker、
  禁止第三 attempt、禁止手工 `run_definition`。

## 计划偏差与修复方向

- 计划假定 2 秒 monitor 命中预算后能够“立即停止 worker”，但当前 monitor 只返回停止判定，控制进程依赖下一次
  agent 调度；这是本次第二 attempt 的直接原因。当前波不改运行时代码，也不重启 worker。
- 后续若继续相同长跑，应将预算 monitor 与 exact worker PID 的停止动作纳入同一受控监督器，并以测试证明
  `stopWorker=true` 后不会再次 tick；该改进不构成对 BF 的重试授权。

## 证据与验证

- BF recovery 状态结果 SHA-256：prepare
  `f4594187cb0bf5a5d997c3e0e35a5647d05454c84c3c0c938c78534dc6f91b85`、schedule
  `30bae8994061177d00e1e60a253926cbe84be420aa50d28626cd983607767e6b`、controls
  `bf223b9b1439b5cc357ca293504618cb128fc5550d9d9701946fa84d679d0dd8`、transfer
  `33da99a4a0fa652c728bcb2a0c691c91f03f060f63713fedca7fddd9c0263c84`、renew
  `c8c5f6af8bf5dee39f626e34c388d730bb09c4db21fcbddd9b04ba7dca9f3f5d`、enable
  `2b50bd86baa0ebc62a593949cc8502c7d51e6c5d66665a341f757cbc1f11036a`。
- 纯 HTTP preflight hash
  `be7a45d09b38f545315c372cb1087a340e0172d9d891083cc1b47430c93d249c`；snapshot worker preflight hash
  `7c59f62e8bf8181b8427317948885afa4df138fe02c3ae82377d9ef2951bcdfc`。
- BF saved recovery、exact guard、terminal monitor 与 snapshot launcher 组合回归 `12 passed`；Python 编译与
  `git diff --check` 通过。

## 下一波

新增 BF two-terminal settlement 方案；只允许在 exact 1 deadline-failed + 1 cancelled-failed、十二 Run running、
Store/link/projection 全零且 worker/18181 停止时执行 rev100 disable。verification 与提交完成后，才可进入 BF
正式退休。
