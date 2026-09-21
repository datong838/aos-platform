# CJ 正式退休与 CK direct successor 验证（2026-09-21）

## 结论

`CK_DIRECT_SUCCESSOR_GREEN`。CJ 以唯一 failed attempt **rev5** 的正式终态完成 disable settlement，九路从
rev231/group258 经 fence 收敛到 legacy rev233/group260；CK 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev234/group261。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `f0fe7f81`；CJ installation `184e0d1d-128a-462c-b677-d19bc5bf0891` / generation
`f45f46a9-56ae-49b5-966d-083cdf19282b`，definition rev175 disabled，唯一 failed attempt
`d0326f13-2ccb-49c0-ade9-0729dc188717` **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev231/group258、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CJ 正式退休

唯一 CJ Host PID 88320 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`69469d23-01f1-41e1-8263-14dbbde43595` succeeded；fence Receipt
`3787f5c3-3dec-4492-aaf1-cf87dabd6ba0` /
`sha256:84627c59ded4fafba6b0f6a00d2e3528294447526723174d164bdb0a8479a54d`，detach Receipt
`54b8272c-dae1-4dca-833e-90a40bc77fba` /
`sha256:9d8812adc4d156ee37149d5791920669c5684915f0399be6030cb358eb14e09d`；
binding rev9/epoch5 disabled，九路 legacy rev233/group260。

## 3/6 CK lifecycle

CK installation `c1cb44ba-68ae-4d32-9974-5f031554fed2` / generation
`1edb1688-e2b6-42f0-b513-849ae372859e` / lock
`sha256:e7b527f80ede65ef8aeade78c0ea29a0199e6986f557e135c547521c4f637e4c`；configuration
`a5f8b32a-d92b-43a0-9afc-3e43d971e3f7` /
`sha256:b01c9641f33da1593ac2e1c2fc031b7a2cee89db5e1ae0c79e1bd8fa069a5196`。
prepare operation `e60b3ca6-bdc2-40a6-9928-5ec574f35917`，唯一外置 Host PID 91080 自然领取；
唯一 verify/configure/enable 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `2a9469c8-12b1-40fa-863d-6787a46507d0`，cutover operation
`4d7f869d-15bd-4246-8f92-7c52e59c7c23`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `4062156b-3688-45af-abe4-db36e2325d56`，resume Receipt
`0f5d0f73-6399-465f-9b59-309059ce1221`；九路全部为 CK extension rev234/group261，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 91080，第二 Host=0、snapshot worker=0、18181=0。以 renewals=10 为 baseline，
38 个只读样本新增 12 次续租，最终 renewals=22、sequence=35；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev175 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `172 passed, 7 warnings`。下一波为 CK saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev176、
recovery58、enable rev177，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。注意上一 attempt 终态为 **rev5**，guard overlay 仍需
predecessor_view revision=4。本提交完成后自动进入该波。
