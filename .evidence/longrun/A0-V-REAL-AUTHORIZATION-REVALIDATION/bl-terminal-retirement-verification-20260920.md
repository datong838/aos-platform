# BL 单终态正式退休验证（2026-09-20）

## 结果

`BL_TERMINAL_RETIREMENT_GREEN`。BL installation
`ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc` / generation
`116d12fc-93bc-4071-a973-fdc6830ea8b1` 已完成正式 detach。

- 唯一 disable operation `7e82992b-0f1b-429f-bcda-36d416ff9cdb` 为 succeeded/phase succeeded
  revision6，expected binding revision6；未重放、未换幂等键。
- Binding 为 rev8/epoch4 disabled/fenced/desired disabled/observed unknown。
- 九路 dispatch 全为 legacy rev164/group191。
- fence Receipt `a3b3cefb-fb83-49e7-b2f5-28f69d3a07ab`，hash
  `sha256:c75a514ccb0239104005302f29e04c41de315d6805ca11e4a1d5e282d1a9c8cf`；
  detach Receipt `3a50db9a-2dec-4543-b37a-701a8e12ee36`，hash
  `sha256:265c6dcf811b6df90e5402fc7f1bc53aad22d8f49d29ec7caffe90f779a40f15`。

## credential 丢失恢复闭环

正常 request 入口在写入前以 `CREDENTIAL_FILE_INVALID` 停止。恢复适配器未伪造 credential 或 trust roots，
而是用容器数据库现有身份建立 `aos_runtime` session，并复用原 `RuntimeDisableService`、
`RuntimeDisableConsumer` 与相同冻结 intent。核心提交后 `claimedByHost=false`、`resendDisable=false`。

三项资源先由 `RuntimeUninstallCleanupExecutor` 固定为 uncertain；Docker 双标识检查证明原容器均 absent，
且 Lease 已过期。随后原 `ExpiredResourceRecovery` 对三个精确 resourceId 调用 `confirm_absent`，均记录
released。原 runtime-apply `319f1b2b-1cdf-49de-bc0c-b9779f018200` 的 unknown cleanup checkpoint 再由
`settle_committed_cleanup` 收敛为 revision65 `failed / PREPARED_RUNTIME_RELEASED`，没有复活 generation。

## 最终边界

- 三资源均 `released / observed_release=true`；runtime pending=0，unresolved=0。
- definition rev118 disabled；唯一 attempt revision46
  `abandoned / ATTEMPT_LEASE_EXPIRED / null`，unexpected attempt=0。
- 十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt=0、`ecom_link`=0、projection pending=0；
  dev-org canary=0。
- 未启动 Runtime Host/snapshot worker，未读取商城源数据，未调用 `run_definition`，未 push。

## 验证

BL retirement 与 credential-loss recovery 专项测试、共享 retirement 回归、Python 编译和
`git diff --check` 均通过；实现与方案及补充恢复设计一致。
