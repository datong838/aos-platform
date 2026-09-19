# AZ 两次 terminal attempt 正式冻结验证

## 前置边界

- snapshot worker 进程=0、18181 listener=0；唯一外部 Runtime Host PID 29815 保持运行。
- exact guard 读回 attemptCount=2：首个 revision 61 为
  `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`，第二个 revision 4 为
  `abandoned / ATTEMPT_LEASE_EXPIRED`，不存在第三 attempt。
- 十二 Run running、十二 Dataset Receipt；Store Receipt、`ecom_link`、outbox、projection pending 均为 0；
  routes=9、live resources=3、canary=0。

## 执行结果

- 共享 pause-terminal 合同仅把 attempt 数量抽为默认 1，AZ wrapper 唯一收窄为 2；AV 默认合同保持 1，
  没有放宽其他历史波次。
- 使用既有 key `a0v-az-saved-snapshot-pause-terminal-v1` 执行一次 pause-terminal；exact abandoned 冻结
  边界下从 definition rev81 enabled 原子推进为 rev82 disabled，hash
  `sha256:685892303ae8c35ea7f921bc95d1d26e179904ca5638a52fc0261bccac5b7789`，`sourceReads=0`。
- inspect 读回 `configurationState=disabled / executionAuthorized=false / routingStatus=disabled / originalGroups=[]`。
  pause-terminal 私有结果 SHA-256 为
  `8ab9fbed4ee8290a759faa229a01a09fc75a32be8c9761766373ebead78b3921`。

## 验证与边界

- AZ exact guard、AZ/AV saved recovery 与 snapshot launcher 组合回归 `15 passed`；Python 编译与
  `git diff --check` 通过。
- 本波未启动 worker、未调用 `run_definition`、未读取商城源数据、未 push、未动其他分支；230 L0 继续挂起。
- rev82 disabled 是下一波 AZ 正式 retirement/detach 的唯一上位 authority；下一波不得恢复本安装的 snapshot
  worker，也不得创建第三 attempt。
