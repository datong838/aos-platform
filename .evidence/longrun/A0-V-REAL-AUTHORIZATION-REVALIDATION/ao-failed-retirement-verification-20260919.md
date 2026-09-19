# AO 失败执行正式退休验证

## 结论

AO installation `d4186607-c93f-4fd0-8daa-46e349184ab9` / generation `00bb99df-d436-483d-86df-496718c6f129` 已经由原 Runtime disable Owner 正式退休。该结论来自实时 binding、resource、route、operation 与 lifecycle Receipt 对账；不是根据测试、提交或计划推断。

AO 的失败执行没有重发，十二个冻结 Run 与 dataset receipt 没有被改变，Store 仍为零提交。下一代 AP 只能消费本次 detach Receipt 作为 direct successor 前驱。

## 前置门禁

`a0v_ao_failed_retirement.py preflight` 只读确认：

- definition revision60 disabled；
- binding revision6 / execution epoch3，enabled/ready，未 fenced；
- 三笔 recoverable Store attempt 精确为 abandoned255、failed11、abandoned2，原因与 error type 均匹配；
- members=12、running Run=12、dataset receipt=12；
- Store Receipt=0、`ecom_link`=0、projection pending=0；
- runtime pending=0、unresolved occurrence=0、tenant running attempt=0、canary=0；
- route count=9，attached revision96 / group revision123；
- resource total=3、released=0。

## 正式 disable 与终态

以幂等键 `a0v-qyh-failed-ao-retirement-20260919-v1-disable` 提交一次正式 disable 请求：

- operation：`44d42ccb-07a2-437a-8405-ea703f812803`；
- accepted receipt：status/phase=`accepted`，expected binding revision=6，`replayed=false`；
- Runtime Host 自然领取并完成，执行器记录 `claimedByHost=true`、`resendDisable=false`；
- operation 最终 status/phase=`succeeded`，revision6；
- lifecycle phases 精确为 `fence → detach`，operations=1、receipts=2。

正式 Receipt：

- fence：`10f92110-608c-43be-b2d4-89a16e424052`，`sha256:524b6736618449f70b52f7e20a25e33ff42cb10ae798387112c18d7ce4f71419`；
- detach：`c98d7a33-2653-42a8-86f1-05f26c09217e`，`sha256:b4e2969a445b0459dd0e43376d600ab87a515374774e3434d31a28eb014c29f9`。

退休后：

- binding revision8 / execution epoch4，disabled、fenced、observed unknown；
- 3/3 resource released；
- 9 条 route 全部回落 legacy，revision98 / group revision125；
- definition 仍为 revision60 disabled；
- 三笔 attempt、12 个 Run、12 个 dataset receipt 与 Store 零提交边界均保持不变；
- runtime pending=0、unresolved=0、canary=0；
- 独立 Runtime Host PID 59258 保持运行，qcursor 保持停止。

## 测试与一致性

- AO retirement / guard / router / saved recovery 与 AL、AM 退休、AO predecessor/successor/cutover 累计回归：57 passed；
- `py_compile`、`git diff --check` 通过；
- 实现仅调用正式 disable service/outbox consumer，未调用 `run_definition`，未重发 disable，未产生外部业务副作用；
- 一次 Receipt 取证查询误选不存在的 `revision` 列并只读失败，随后按实际 schema 重查成功；无写入或状态变化。

本波完成的是 AO 失败 generation 的正式退休，并不表示 recoverable Store、经营参谋自然首链或八工作台真实业务完成。下一波以 detach Receipt `c98d7a33-…` 建立 AP direct successor，继续复用冻结的十二源，不回读源数据。
