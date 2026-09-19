# AY 过期 enable 结算与未激活退休验证

## 结论

`AY_STALE_ENABLE_RETIREMENT_GREEN`。原 enable
`24a85b28-f00d-43cf-ba5d-28f064c74f6a` 未恢复、未重发，已由正式 DisableService 同事务改为
cancelled@revision2；独立 disable `59bd67eb-92c3-4da9-8584-c084d081d027` 正式 succeeded@revision6。
AY 随后通过既有 configured-unactivated authority 退休为 uninstalled@6，不存在伪造的 dispatch detach。

## 正式控制证据

- preflight 固定 active@etag5、Binding rev3/epoch2 disabled/fenced、配置
  `ce24590a-479e-4a5e-94ab-01d138e0675c` rev1/hash
  `sha256:579a652e471f626f08e25f80f19b4e9f77b91531a456dac87ef2f2220e1cff89`、三资源 released。
- disable 请求在 `2026-09-19T13:28:25.703638Z` 接受并同事务完成 cancellation/fence；Binding 到
  rev4/epoch3 draining。唯一既有 Host 随后自然完成 draining/committing/disabled_committed/succeeded，Binding 到
  rev5/epoch3 disabled/unknown/fenced。`disabled_committed` hash 为
  `sha256:90f979526e47744a9fdcd9df6190472f400e67c6ce29d3c2d47ed3c17dec3937`。
- AY 从未 register/cutover，故该 disable 的 dispatch lifecycle operation/Receipt 均为 0，九路保持 legacy
  rev125/group152；这是正确的未激活结算，不用空 detach Receipt 冒充接入后退休。
- 第一次卸载因管理连接不满足专用非特权应用身份而事务回滚；切换到既有 0600
  `aos_a0v_installation_20260912` 身份后，同一冻结 key 正式提交。回读失败发生在提交后的本地预期断言，随后仅只读
  对账，没有第三次发送 uninstall。
- configured-unactivated Receipt `48fc0e55-578d-46ae-b45a-bf8ab8085823`，content hash
  `sha256:21494a12aed250565b7f65cf4b8da0a36a5d9d9c8c9cbb433bd2346734df4409`；authority 精确记录
  bindingRevision6、上述 disable operation、releasedResourceCount3、successfulEnable/dispatch/businessExecution
  全部为 0。最终 Binding rev6/epoch3 uninstalled/stopped/fenced。

## 现场偏差与闭环

停止 PID27382 后，launchd 项 `com.aos.a0v-runtime-u` 仍以 replacement-T 状态文件维持唯一 Host；它领取本波
disable，而非第二 Host。直接 TERM 后该项以 PID29041 自动拉起，证明之前“Host 已为 0”的判断不完整。现已对精确
launchd 项执行 bootout，再次进程读回为 0；definition 仍 rev79 disabled。该偏差没有产生 AY enable、register、
cutover、attempt 或业务写入。

最终边界仍为 12 个 saved running Run、12 个 Dataset Receipt；AY attempt=0，Store Receipt=0、`ecom_link`=0、
projection pending=0、`dev-org/dev-project` canary=0。未读商城源数据，230 L0 挂起，未 push。

## 私有证据与验证

- preflight/result SHA-256：`99c9fe1e1d95d432c42a755d4095881fbb9e8cc74bee1e4f59437f812f6b1344`
- request-disable/result SHA-256：`44fdefd7a3983a3e4580d827b9b9eb487babcaddd6693573b5d27a158ce6b9df`
- process-disable/result SHA-256：`d6d880f38dff3c1b197011a34fa45c01b91e74368ece200fb0a24397eeea8fec`
- retire/result SHA-256：`0b683410334a26369df67f4525f66370648f27840aa20d399bc26d85fa6300fa`
- audit/result SHA-256：`d72e26a93e233047326ae40d0563757fa9f480b8a7607c1870d4e7b1d9950cb8`
- AY 窄执行器与既有 stale-enable 合同回归通过；Python 编译与 `git diff --check` 通过。

下一波只允许从 AY configured-unactivated Receipt 与 legacy rev125/group152 创建 AZ direct successor；先 plan，
后执行。不得复用 AY identity、原 enable 或已经 bootout 的旧 launchd 项。
