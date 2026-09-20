# BN 正式退休与 BO direct successor 验证（2026-09-20）

## 结论

`BO_DIRECT_SUCCESSOR_GREEN`。

BN released-owner 边界已通过正式 disable consumer 收敛为 exact detach；BO 仅以该 detach Receipt
为 predecessor 创建、启用、注册并完成唯一九路 cutover。12 次新增 lease renewal 观察通过，definition
rev118 持续 disabled，未产生 runtime attempt、商城源读取或业务副作用。

## 1. BN 正式退休

- installation `d89bca67-4472-4b43-b0bd-ae8a2e0459f5`，generation
  `a43b3e64-7bb4-454c-822e-58bc13acbcaa`；
- disable operation `ff01e6a5-436a-46b1-a757-8e78b3344748` succeeded；首次 consumer
  已完成数据库提交后，本地旧 epoch4 断言失败；随即仅做 readback，确认 binding rev9/epoch5，未重发；
- fence Receipt `ca296d29-9f02-4567-a539-bc14abdf22ca`；detach Receipt
  `f581970a-fcff-403b-ad64-57c26e38831e` / hash
  `sha256:ec476774123dea036e212e6164b471510a4a536c3cf2ff137149d0437dc038d4`；
- binding rev9/epoch5 disabled/fenced/desired disabled/observed unknown，三资源 released；
- 九路回到 legacy rev167/group194；completed reconcile 明确 `resendDisable=false`。

## 2. BO 创建与 lifecycle

- installation `307399a0-21bb-4d55-95b2-8b0fee238913`，generation
  `030bf59c-c998-4ee6-aedb-11d8d7d5831a`；
- lock `sha256:0e6dc143f25c8dc043b30b324719cce42c37dcb7bde08b51b0add161a70c860f`；
- configuration `b7ed1c14-9cd1-4c78-95ea-c46ac80742d8` / hash
  `sha256:3bee220829bb407782f5363541fff57731434d29d06c02236ceb8565f04260b3`；
- prepare `878d3c80-038a-43f7-b011-61ceb8ad0ae0`、verify
  `93e6ec8e-bfae-4e48-9515-de8ae7f03559`、configure
  `da8f5824-4315-4ca0-83b8-fe2d8a5c1afd`、enable
  `d5e76e5e-157e-4d29-85ed-b7c955cc9bb9` 均 succeeded；
- 最终 head active etag5，binding rev6/epoch3 enabled/unfenced/ready，三资源 pending且未释放；
- 全程仅一个外置 Runtime Host，第二 Host=0。

## 3. successor 注册与 cutover

- registration Receipt `2d970241-722b-478c-b0b9-d947890f8f4f`，request hash
  `sha256:6a4cb14fa48a6d7174a41ea685544c80d43c41a44950d3ffee90a7d916dc9388`，
  content hash `sha256:ef773d362814958a412cc4f8cc2f7343a0b412a2f29c16080c3ed535bcd3b04e`；
- cutover operation `66528958-480d-4e5d-a439-5093e51b31d9` 串行完成 approve、prepare、pause、
  commit、validate、resume；
- prepare/commit/validate/resume Receipt分别为
  `62511980-600a-4733-8b2b-4a0d4d410a2b`、
  `834c3175-acbb-47be-8efc-7a953e503707`、
  `4ac72c6b-ebc9-445b-b09d-3902fedd7476`、
  `12c4be68-0b4e-4cbf-b837-095b9663d7b4`；
- 九路最终均为 BO extension rev168/group195、epoch3、fence=false；claimPaused=false；
  claimed occurrence/attempt、unknown attempt、running runtime attempt 均为空。

## 4. 健康观察与零副作用

- renewal baseline 6，最终 18，新增 12；37 个只读样本，约 12 分钟观察窗；
- 最终 operation sequence 31，三资源共同续期至 `2026-09-20T10:04:33Z` 之后；
- definition rev118 始终 disabled；extension attempt=0、running=0、unresolved=0、runtime pending=0；
- 十二成员、十二 saved Run、十二 Dataset Receipt 保持；Store Receipt=0、`ecom_link=0`、
  projection pending=0；`dev-org/dev-project` canary=0；
- 未调用 `run_definition`，未读取商城源数据，230 L0继续挂起。

## 5. 验证与方案一致性

- 专项测试：7 passed；
- 五个本波 Python wrapper 编译通过；
- 最终 `observe`：`BO_REPLACEMENT_OBSERVED`，BN exact detach 与 BO ready 同时读回；
- 只修改 wrapper、专项测试与证据文件，未修改共享生产实现；
- plan 中的串行步骤与实际执行一致。唯一执行期纠偏是 binding epoch4→epoch5：这是正式 detach
  语义的预期增量，已在只读 readback 后更新断言，没有重发或绕过 owner。

## 6. 下一波

自动进入 **BO saved-snapshot recovery**：保持当前唯一外置 Runtime Host 存活；纯 HTTP 18181 与其并存，
读回 Cron=false、snapshot worker=false、进程内 Runtime Host=false，且外置 Host 总数仍为1（第二 Host=0）。
随后按 transfer/recovery/enable 的新 revision 链启动唯一自然 attempt，并观察至正式终态。
