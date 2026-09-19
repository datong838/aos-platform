# BE 保存快照恢复、单 attempt 终态与冻结验证

## 配置与 authority 转移

- definition rev94 disabled、BE attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev94 disabled 生成 BE rev95 disabled，hash
  `sha256:72e96fef73543e48726164821a06308a3b3a2311bb9c045bb1140479f067fd86`。
- renew 从 recovery rev30 生成 rev31，hash
  `sha256:7c91fba851b178bf52c44116c3cda5309ccd2aba9539b7e7081c598350b7d373`；同一事务生成
  definition rev96 enabled，hash
  `sha256:9a434ecb65b4b73ac0dc15fc9e4edb4931b0816eb9b210f8ce14ea0cf6185882`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与唯一终态

- 创建 exact `A0V-BE-SNAPSHOT-WORKER-20260920` deployment lease 后启动唯一自然 snapshot worker；读回
  worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 唯一自然 attempt `041843a3-2cf0-4211-bc16-00e823c210bc` 使用幂等键尾号 `:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租至 revision 60；
  只读 monitor 以数据库 `accepted_at` 为起点，在 elapsed=1800 秒命中预算并立即停止 exact worker。
- worker 端口随首个 SIGINT 释放；进程进入 STOPPING 后未在第二次 SIGINT 与 TERM 后退出。唯一 attempt 已由外部
  Runtime Host 正式收敛后，才对 exact worker PID 65728 使用 KILL 清理残留解释器；唯一外部 Host PID 29815
  未受影响，也未产生第二 attempt。
- 同一 attempt 于 `2026-09-19T22:25:14.544122+00:00` 正式收敛为 revision 61
  `abandoned / ATTEMPT_LEASE_EXPIRED`。exact guard 固定验证 attemptCount=1、十二 Run 仍 running、十二 Dataset
  Receipt 保留；relationship=1、link command=1、linkCount=1168；retirement=0、Store Receipt=0、`ecom_link`=0、
  outbox=0、projection pending=0、BE 九路与三资源保持、`dev-org/dev-project` canary=0。

## 冻结结果

- `pause-terminal` 在唯一 `ABANDONED_FREEZE_BOUNDARY` 下把 definition rev96 推进为 rev97 disabled，hash
  `sha256:1b72309601d8e0670ec47785c1ee30d0d69db4708bc4ccb2ce187febddb3a925`；最终读回
  disabled/executionAuthorized=false，`sourceReads=0`。
- snapshot worker 最终进程不存在、18181 无监听；唯一外部 Runtime Host PID 29815 继续运行，临时 worker lease
  已移除。本波没有商城源读取、没有手工重发、没有切换幂等键、没有 push，230 L0 继续挂起。

## 计划偏差与风险

- terminal 未在 1800 秒预算前发生，监督在 elapsed=1800 秒按方案先停 worker；外部 Runtime Host 随后仅将同一
  attempt 收敛为 lease-expired abandoned，符合预算先到路径。
- worker 应用端口已在 SIGINT 后释放，但解释器未完成自然退出；在 attempt 正式 terminal 后才精确 KILL 该 PID，
  未扩大到 Runtime Host 或其他进程。后续应单独调查 snapshot worker shutdown hang，不在本波改变运行时代码。
- 本波执行与证据边界无未知提交；后续退休波必须以 exact rev61 abandoned + definition rev97 disabled 为
  authority，不得在 BE 内恢复 worker或创建第二 attempt。

## 证据与验证

- BE recovery 状态结果 SHA-256：prepare
  `da6392a76a95bd8aa1faee5b0c4921166bab31471281e25a7331d8b09204f91e`、schedule
  `c70e890ca02a2a82dfa1f452b86dd7d4723cb60f7ab11da904807611595f9668`、controls
  `de8d01fbd1f6e5c7adc13ac30b4d0eaec9bfb3219415391b430e35aa9e4d163e`、transfer
  `19d53d2ff59e21955f78ce3d4be438a9a622c15152d9c758e1b13eecc0ffde2b`、renew
  `216c585c8f92e8a2c014cf7f3dadb7fec2637e27890d0afa58b0206349afe4c7`、enable
  `ed5808340a75fe68b5385116eb74c18bea5b087910b37ca1476de67eef25d72a`、pause
  `ec97d3c5eaa610e77cd0a111beab6cdcc3fc51a4c0ffd92276d0d53347f54b7a`。
- 纯 HTTP preflight hash
  `7689b38f2cb5aee80be7972d83da9ba3be303f1bf223c90c7227ac331ef87979`；snapshot worker preflight hash
  `31abbf97b53f3d1954349581f28d46e279ef94d8027ab6524ec7f4c7e42bc35f`。
- BE saved recovery、exact guard、terminal monitor 与 snapshot launcher 组合回归 `12 passed`；Python 编译与
  `git diff --check` 通过。

## 下一波

新增 BE terminal retirement 方案；只允许在 exact 单次 abandoned、definition rev97 disabled、十二 Run running、
Store/link/projection 全零且 worker/18181 停止的边界下执行正式 retirement。verification 与提交完成后，才可进入
BF direct successor。
