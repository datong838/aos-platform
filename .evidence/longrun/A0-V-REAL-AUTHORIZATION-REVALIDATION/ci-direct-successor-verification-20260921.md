# CH 正式退休与 CI direct successor 验证（2026-09-21）

## 结论

`CI_DIRECT_SUCCESSOR_GREEN`。CH 以唯一 failed attempt 的正式终态完成 disable settlement，九路从
rev225/group252 经 fence 收敛到 legacy rev227/group254；CI 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev228/group255。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `b7bd7a43`；CH installation `990f96f7-764e-4002-b691-fc5eb8d4335c` / generation
`0521ccf8-304a-45b3-b820-dc6ebd64b51b`，definition rev169 disabled，唯一 failed attempt
`0be8900c-4e4f-41c7-a93b-7dbfecb2bfe6` rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev225/group252、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CH 正式退休

唯一 CH Host PID 83095 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`2c28623c-d418-4123-8846-89f4c4d905e9` succeeded；fence Receipt
`9ab9ad0a-f85a-4dd0-b91d-5a946a0766ea` /
`sha256:de6b9e804ec6131206fd23d0919d8bc26e0e93a680baec34b9b826d9fa180268`，detach Receipt
`bef972d2-2c5f-4cd3-9448-b7e94ff7594d` /
`sha256:c1537c4af534489422e2fbe819d7ed079db9c25c9d1702d214c77097af8ffdac`；
binding rev9/epoch5 disabled，九路 legacy rev227/group254。

## 3/6 CI lifecycle

CI installation `1b9f500d-48a0-4f2c-8284-3db26e5cd4e7` / generation
`8de8994b-ad87-4039-a851-d944153bca08` / lock
`sha256:06757616841bff14cebd4175476baa08d8ebd1fd81a5ce06cd1b2abb968af759`；configuration
`d89f31f4-e9ee-4026-bb0a-b3d9e14e17f0` /
`sha256:2aaf0762c81e038b67bc2a10b0b30b5acb28a731c1324063577a4a94c28b468e`。
prepare operation `473dc4ab-42af-4dbd-95bf-67beaa6a1f3e`，唯一外置 Host PID 85436 自然领取；
唯一 verify/configure/enable 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `54f4303a-3ddc-4291-843f-270966407257`，cutover operation
`92bdd589-90d4-4e66-817d-1cb05ebfbd1d`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `bedfd44d-ae8e-4951-8734-e69c847f415a`，resume Receipt
`34884773-f9f1-4fad-8e62-9499ed8c7916`；九路全部为 CI extension rev228/group255，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 85436，第二 Host=0、snapshot worker=0、18181=0。以 renewals=3 为 baseline，
36 个只读样本新增 12 次续租，最终 renewals=15、sequence=28；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev169 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `158 passed, 7 warnings`。下一波为 CI saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev170、
recovery56、enable rev171，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。本提交完成后自动进入该波。
