# CI 正式退休与 CJ direct successor 验证（2026-09-21）

## 结论

`CJ_DIRECT_SUCCESSOR_GREEN`。CI 以唯一 failed attempt 的正式终态完成 disable settlement，九路从
rev228/group255 经 fence 收敛到 legacy rev230/group257；CJ 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev231/group258。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `3427bc3e`；CI installation `1b9f500d-48a0-4f2c-8284-3db26e5cd4e7` / generation
`8de8994b-ad87-4039-a851-d944153bca08`，definition rev172 disabled，唯一 failed attempt
`4c67a2b5-34a6-47f7-9cc6-e59ce718d491` rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev228/group255、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CI 正式退休

唯一 CI Host PID 85436 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`33240efc-8111-49ef-ac0c-759ae37868cc` succeeded；fence Receipt
`62ea17ba-7db6-4243-a749-6f926adc9f36` /
`sha256:6afca324927a4067370962c7891a03cf253bed4e576b06db2fb0cb4d5c988760`，detach Receipt
`700c9914-c3ed-4360-8769-5f8d09307352` /
`sha256:5cc5d6e9cf6a284f6e9533438f225291042162573aee209ff9b9cbc20893c4dd`；
binding rev9/epoch5 disabled，九路 legacy rev230/group257。

## 3/6 CJ lifecycle

CJ installation `184e0d1d-128a-462c-b677-d19bc5bf0891` / generation
`f45f46a9-56ae-49b5-966d-083cdf19282b` / lock
`sha256:f96d6d2a702e0b4847ae259233fc50976ca5763462eb975359b5344edf758537`；configuration
`9bcc61bc-2e5d-414c-a7ce-62a6b94a2639` /
`sha256:633c115825d577437d5b11c3e33d19644077bb9efbc0e2f627b862fc61ae3302`。
prepare operation `8a148985-7582-4c10-b514-cc7e01359ac0`，唯一外置 Host PID 88320 自然领取；
唯一 verify/configure/enable 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `08148835-4ac9-4106-a9cf-6c727f83f1ec`，cutover operation
`82b2884f-7625-47d5-a531-ea32c9ed6f14`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `22105910-2b87-4144-a382-f3d11ef3a1ed`，resume Receipt
`a5378075-cf50-4a5e-b51c-eaa1cbd291c9`；九路全部为 CJ extension rev231/group258，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 88320，第二 Host=0、snapshot worker=0、18181=0。以 renewals=3 为 baseline，
35 个只读样本新增 12 次续租，最终 renewals=15、sequence=28；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev172 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `165 passed, 7 warnings`。下一波为 CJ saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev173、
recovery57、enable rev174，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。本提交完成后自动进入该波。
