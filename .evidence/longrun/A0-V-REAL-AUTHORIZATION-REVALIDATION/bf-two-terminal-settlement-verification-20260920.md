# BF 两次 terminal attempt 正式冻结验证

## 前置边界

- snapshot worker 进程=0、18181 listener=0；唯一外部 Runtime Host PID 29815 保持运行。
- exact guard 读回 attemptCount=2：首个 revision61 为
  `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`，第二个 revision10 为
  `failed / RECOVERABLE_INGRESS_CANCELLED / IngressJournalConflict`，不存在第三 attempt。
- 十二 Run running、十二 Dataset Receipt；Store Receipt、`ecom_link`、outbox、projection pending 均为0；
  routes=9、live resources=3、canary=0。

## 执行结果

- BF exact guard 只接受上述两个固定 identity、同一 request hash 与 `:1`/`:2` 幂等键；BF wrapper 唯一将
  pause-terminal attempt 数量收窄为2，共享默认合同仍为1，没有放宽其他历史波次。
- 使用既有 key `a0v-bf-saved-snapshot-pause-terminal-v1` 执行一次 pause-terminal；exact 双 failed 冻结
  边界下从 definition rev99 enabled 原子推进为 rev100 disabled，hash
  `sha256:384b194f2328f6b996fa60fcf07c3e699f8294073255618bd84e42b3e0118fb6`，`sourceReads=0`。
- inspect 读回 `configurationState=disabled / executionAuthorized=false / routingStatus=disabled / originalGroups=[]`。
  pause-terminal 私有结果 SHA-256 为
  `5689e938a8f980a5b1167f619e73ca80134445aa28aa002354b3549037cc595f`。

## 验证与边界

- BF exact guard、BF/AV saved recovery 与 snapshot launcher 组合回归 `11 passed`；Python 编译与
  `git diff --check` 通过。
- 本波未启动 worker、未调用 `run_definition`、未读取商城源数据、未 push、未动其他分支；230 L0 继续挂起。
- rev100 disabled 是下一波 BF 正式 retirement/detach 的唯一上位 authority；下一波不得恢复本安装的 snapshot
  worker，也不得创建第三 attempt。
