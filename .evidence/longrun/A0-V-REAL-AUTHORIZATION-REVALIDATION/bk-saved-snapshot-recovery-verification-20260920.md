# BK 保存快照恢复、暂停终态与单 attempt 冻结验证

## 配置与 authority 转移

- definition rev112 disabled、BK attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。重启前外部 Runtime Host 唯一 PID 10991，第二 Host=0。
- prepare、schedule-ingest、controls 成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 在
  transfer 前关闭且 18181 已释放。
- transfer 生成 definition rev113 disabled，hash
  `sha256:1facf21e8c64a36c517a32411c97aa13f97b65c5e6de1a905d4e7f80be7666d4`。
- renew 生成 recovery rev37，hash
  `sha256:4c09de3b7a1b7f38bcbe3cb78be1a3c951ed8323e4899cc9e7e7506a7db598f4`，同事务生成
  definition rev114 enabled，hash
  `sha256:2eb73dd4f842522dd16658687774d52f8b9d197471c4be9147411f34a35e1738`；enable 读回
  `executionAuthorized=false / original_group_pending / sourceReads=0`。

## 唯一自然 attempt 与用户暂停边界

- exact lease `A0V-BK-SNAPSHOT-WORKER-20260920` 建立后，supervisor 以50秒间隔启动唯一自然 worker
  PID 35232；worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 唯一 attempt `c0b032b7-30c1-4260-9b67-99e298347dea`，幂等键
  `snapshot-group:c5ff1926-45b0-56de-b6b3-07d5b7d053a1:1`，request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`，健康续租至 revision13。
- 用户明确要求暂停并重启时，监督器只停止 exact worker 进程组；18181 释放。数据库于
  `2026-09-20T06:28:51.573542Z` 将该 attempt 正式终结为
  `failed / RECOVERABLE_INGRESS_CANCELLED / IngressJournalConflict`。这是已知且可解释的正式终态，
  attemptCount始终为1；未恢复 worker、未产生第二 attempt、未手工重发。
- 重启后先只读对账，再以 exact ID、request hash、rev114/recovery37、九路 rev159/group186 和零副作用
  边界限定该 cancelled 组合，映射到既有失败冻结闭包；其他 reason/error 继续 fail-closed。

## 冻结与禁用边界

- exact guard 读回十二 Run running、Dataset Receipt=12、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、dev-org canary=0、九路 BK route current，判定 `FAILED_FREEZE_BOUNDARY`。
- `pause-terminal` 仅在 exact terminal、attemptCount=1 与零副作用边界成立时执行，生成 definition rev115
  disabled，hash `sha256:ffd4f2afc20c438ffa0820cfbb9ac6068051a6cb641069c67d3b18c2ff840735`，
  `sourceReads=0`。
- 重启后 snapshot worker与临时18181均为0；系统重启也停止了外部 Runtime Host，因此当前 Host=0，
  后续波若需 Host 必须按下一波方案重新建立唯一实例。没有商城源读取、没有 push，230 L0继续挂起。

## 私有证据与回归

- 纯 HTTP preflight `292f5efaf6f28d4db9137f4ac71b441f714c78aad03150a8c74b551014dc3bda`；worker
  preflight/status `41906abb61feacadc494440b6949c6b9ab0c33f059115a1de9396a5313f04a57` /
  `7dad6d4535f35f84c7fe08f2f3eafc3f915abb9f1150582aa44bf351e29b3ec7`。
- prepare/schedule/controls `4036154885d1932ca45de945e1022bb4bd7621400cf80471d4d85c9e1e3caedc` /
  `52105385f66f74ff49dfa3e520f3c6ebdc8dc2be2ec8cb550d739f7d51f77309` /
  `63fcfc3c4b1a25c8ee8efaed2e3e19f259d6f623705a871b97aec499abb6945a`。
- transfer/renew/enable `95e32791116fae81b4a8dc146ce844f7d649eb88fd71fe90ada7b8465694f7c8` /
  `40e9d8b0f33d3ab5d12c257a42437ac912435675368096cbeee03470d33d52dc` /
  `8ae29520d824a20f49c33d75e22c61ee5e41cc4a33f3053004602c12b60a4c60`；pause-terminal
  `8e5cf4625e2c673db49af6f5e081fe37d43bad34854cbc60a88feb1623b6ae7b`。
- BK saved recovery、exact guard、supervisor与snapshot launcher专项回归通过；Python编译与
  `git diff --check` 通过后收口。实现、方案、暂停终态与零副作用边界一致。

## 下一波

新增 BK terminal retirement 方案；仅在 exact 单次 failed terminal、definition rev115 disabled、十二 Run
running、Store/link/projection全零且 worker/18181停止时执行正式 disable/fence/detach。verification与提交后，
自动进入 BL direct successor。
