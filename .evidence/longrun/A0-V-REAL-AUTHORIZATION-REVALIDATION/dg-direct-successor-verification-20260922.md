# DF 正式退休与 DG direct successor 验证（2026-09-22）

## 结论

`DG_DIRECT_SUCCESSOR_GREEN`。DF 以唯一 failed attempt rev4 完成 disable settlement，九路从
rev297/group324 经 fence 收敛到 legacy rev299/group326；DG 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev300/group327。DG configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `53362fe4`；DF installation `a0639f78-af04-4249-97f6-d8507de45f44` / generation
`ec18c8c6-2694-44c1-a9c9-ea79ea606e45`，binding rev6/epoch3，definition rev238 disabled，
唯一 attempt `20318703-942c-49da-8d3b-98409c590c05` failed rev4。基线为十二 Run/Receipt
与零副作用。

## 2/6 DF 正式退休

Host 79478 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`06664a6c-c6da-4ecd-80e7-87b0b1ade018`，detach
`6c1dbb1e-6aec-4276-97fd-5bf7ee90ae03` /
`sha256:a7cecfce6cd17074fcff0ce9feec405d5d95eaf1a117466b2a4b5db7f3f51330`；binding
rev9/epoch5，九路 legacy rev299/group326。claimedByHost=false。退休 preflight 前未创建
`replacement-dg`。

## 3/6 DG lifecycle

DG installation `d551d104-f240-4b27-b738-1ef47129b5a4` / generation
`6c1780ab-746b-4303-a9ad-dc30039af8a4` / lock
`sha256:63f93357f433f7b9c85c0316eb746ea66b61642b00cde388fabde339a33312a2`。prepare
`8f8be2e1-3655-4a53-bfb6-0d2de164ebfe`；configuration `6611514e-e940-4df3-a7bf-bff441a5bc37`
rev1/hash `sha256:c5c763bb916f9893de57dafea8c44b96e5996157c87e0fbea9079c9f2078a757`，policyRef
RuntimePolicy rev11。唯一 Host PID 82684，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-dg-successor-v1`。cutover
`0c292cdc-7cbb-4e9b-8d9b-a5493ea1fbe3`。九路 rev300/group327。

## 5/6 唯一 Host 健康观察

Host 82684 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 6，82 samples，
renewals 18/sequence 31，delta +12。binding rev6/epoch3 enabled/ready，attempt=0。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 DG saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
