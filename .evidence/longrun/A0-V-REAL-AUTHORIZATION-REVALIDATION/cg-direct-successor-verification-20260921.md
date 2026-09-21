# CF 正式退休与 CG direct successor 验证（2026-09-21）

## 结论

`CG_DIRECT_SUCCESSOR_GREEN`。CF 以唯一 failed attempt 的正式终态完成 disable settlement，九路从
rev219/group246 经 fence 收敛到 legacy rev221/group248；CG 仅凭 exact detach Receipt 创建、启用并
cutover 到 rev222/group249。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `5cd096bb`；CF installation `8cf0c597-cf81-4fa5-b1ff-f27e3537a94c` / generation
`88996259-ad79-4aa6-962c-c29a24559db8`，definition rev163 disabled，唯一 failed attempt
`d16e9452-0f4b-40cc-97f0-316841dfee29` rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev219/group246、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CF 正式退休

唯一 CF Host PID 73889 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`0858ea02-0d34-49dc-b2c4-4276b31c72b7` succeeded；fence Receipt
`61aecb4c-8241-4813-9d48-97276cc5a571` /
`sha256:0de5fa8ecf58de8a692538a0e2c20150e07cbffffacd087032df367d774da626`，detach Receipt
`829cd86a-bf4e-4b62-a0e8-e3a89c34b9e0` /
`sha256:0f2adfef50c42ed684a0ccdedf737a9a13a9e31b55d7b778b08f3f49e1bb2f6b`；
binding rev9/epoch5 disabled，九路 legacy rev221/group248。

## 3/6 CG lifecycle

CG installation `8f42819c-0fc7-48cf-a5c4-9ba96894a6f5` / generation
`3ed300fa-5fff-4949-9fb0-1926412e51ae` / lock
`sha256:554edd86332cff3f2879d4167f2ae7b16f4836af736dd3ff2545b66a57a3438d`；configuration
`9ff22648-bbe3-4894-8ffd-fd85320e9a6b` /
`sha256:5ed349c44c4af8f61c4a0cf6dc0f6e328bed49a52ef3b37ffd947093fd3c740f`。
prepare operation `a5b894bb-0a51-4487-a738-651c60ac7505`，唯一外置 Host PID 77505 自然领取；
唯一 verify/configure/enable 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `0f90399d-d3b0-4efb-adf4-4b4e7bc52059`，cutover operation
`d8dbb6b2-7fdf-424a-b95f-63513ca37e06`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `ef4b083f-ab08-4779-9592-f7ab2de35230`，resume Receipt
`0672dce0-e632-4863-94af-0d6325110de9`；九路全部为 CG extension rev222/group249，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 77505，第二 Host=0、snapshot worker=0、18181=0。以 renewals=15 为 baseline，
35 个只读样本新增 12 次续租，最终 renewals=27、sequence=40；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev163 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `144 passed, 7 warnings`。下一波为 CG saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev164、
recovery54、enable rev165，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，并按既定
fail-closed/1800 秒规则收敛。本提交完成后自动进入该波。
