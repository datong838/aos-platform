# AT 保存快照恢复失败边界、正式退休与有界执行修复验证

## 自然执行终态

AT installation `631e6d01-a5bb-4865-95eb-07d5665ed957`、generation
`63ea2c87-f185-4b02-b792-1e3073db4a1b` 在 definition rev72 enabled、recovery rev23 下由自然 worker
领取，未调用 `run_definition`。同一 generation 共产生四个自然 attempt：

1. `9377beaa-9408-483c-95bb-b432c7aefc70`，ordinal 1，rev11 failed，
   `RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`；
2. `b7fd50e2-91a8-40a3-8585-0895404d5a5f`，ordinal 2，rev11 failed，原因相同；
3. `e512e4d8-25e0-41e0-b624-8b47a3037db2`，ordinal 3，rev11 failed，原因相同；
4. `0b142866-7a0d-483c-b103-523c1612d425`，ordinal 4，rev5 failed，
   `RECOVERABLE_INGRESS_CANCELLED`；该笔由关闭旧 worker 后的取消信号终结，用于阻止同一失败条件继续无界重试。

前三笔均持续推进 heartbeat 与 Lease，但真实 1168 条关系处理不能在原 300 秒绝对上限内完成。四笔终态的共同
副作用边界为：12 个 Run 仍为 running、12 个 Dataset Receipt 保留、relationship=1、link command=1、
linkCount=1168；relationship retirement=0、原幂等键 Store Receipt=0、`ecom_link`=0、projection pending=0、
outbox=0、`dev-org/dev-project` canary=0。未知结果没有重发。

## 失败暂停与正式退休

- AT definition 从 rev72 enabled 更新为 rev73 disabled，定义 hash 前缀为
  `sha256:76a5cda8`；旧自然 worker 已正常退出，18181 已释放。
- 正式 disable operation 为 `5d69615c-2e9f-4ad5-8725-14a9e1fefd76`，审计结果
  `AT_FAILED_RETIREMENT_GREEN`。
- AT Binding 终态为 rev8/epoch4、disabled、fenced、observed unknown；3/3 runtime resource 已 released。
- 九条路由全部回到 legacy，extension revision113、cutover group revision140；running attempt、unresolved、
  runtime pending 与 canary 均为 0。
- 退休后 definition 保持 rev73 disabled，Store Receipt、live `ecom_link` 与 projection pending 继续为 0。

## 有界执行修复

保存输入恢复的最大执行时间从固定 300 秒提升为固定 1800 秒；heartbeat 30 秒、Lease 120 秒、取消信号、
有限数校验和最大值校验保持不变。snapshot worker 直接引用 recoverable Store 的统一上限，避免两处预算漂移。
受控 18181 profile 另外显式设置 `AOS_SNAPSHOT_GROUP_WORKER_ENABLED=false`，确保配置用 HTTP 进程不会自然领取
attempt。

本改动只扩大合法自然执行的有限时间窗口，不改变幂等键、Store 写入顺序、租户范围、预算审批、失败终态或重发
规则。1800 秒后仍未完成会继续 fail closed。

## 验证与清册状态

- AT saved recovery、attempt guard、failed retirement、recoverable Store、snapshot worker lifecycle 与受控 API
  本次复核：`48 passed`；修改期间更宽的累计组合曾为 `53 passed`。
- Python 编译、文件级差异和方案/代码一致性复核通过；本波未读取商城源数据、未产生 Store/ecom 外部副作用、
  未 push，230 L0 继续挂起。
- AR2 阶段验证器当前扫描 1988、分类 200、迁移 93；forward dependency、reverse caller、bundle cross-layer
  三类错误均为 0。验证器同时报告 37 个历史清册 hash 漂移和 9 个 dynamic-reference hash 漂移；这些对象不在
  本波文件级修改清单内，因此本波不篡改清册 hash，也不把该结果表述为 closure green。
- 浏览器复验待 AU successor 恢复 API 后执行；当前 18181 离线是 AT 正式退休后的预期状态，页面不得据此触发写操作。

## 下一波

以 AT 正式 detach/retirement Receipt、legacy revision113/group140 和 definition rev73 disabled 为唯一上位权威，
方案先行创建 AU direct successor。完成 installation/generation、签名配置、replacement、注册、九路 cutover、
saved snapshot transfer/renew 后，使用已加载 1800 秒修复的新自然 worker 执行一次非空真实恢复；只读观察至
succeeded 或明确失败终态，禁止手工 definition、禁止重发未知结果。
