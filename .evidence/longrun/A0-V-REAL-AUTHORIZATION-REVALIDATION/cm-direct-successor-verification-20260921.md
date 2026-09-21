# CL 正式退休与 CM direct successor 验证（2026-09-21）

## 结论

`CM_DIRECT_SUCCESSOR_GREEN`。CL 以唯一 failed attempt **rev5** 的正式终态完成 disable settlement，九路从
rev237/group264 经 fence 收敛到 legacy rev239/group266；CM 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev240/group267。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `8ca0558a`；CL installation `64e49f66-b0ef-4676-91c1-eb05f6d1d0b1` / generation
`a583218d-f65b-4697-9e60-7281a0bff66e`，definition rev181 disabled，唯一 failed attempt
`bf2ff936-6c93-4712-93cb-30dd312f11eb` **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev237/group264、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CL 正式退休

唯一 CL Host PID 94133 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`a4b94187-2a96-4779-af57-02e4b659a90d` succeeded；fence Receipt
`8f7d77cd-d068-407f-9dc8-8e2f0141647a` /
`sha256:555f4b32d7ef24d217dd96a7444e76f6323811854d82acaa2b054bc9c8c0c6f5`，detach Receipt
`03e11531-9fb5-4453-80dd-2d2d07051bec` /
`sha256:b93907af1a3ace36e10d83da4e199da17c80aaa0b9cdbc557b88a54fed721992`；
binding rev9/epoch5 disabled，九路 legacy rev239/group266。

## 3/6 CM lifecycle

CM installation `b52c8e1c-a343-4ef4-b106-38d859ba9677` / generation
`d3ec88cc-a05a-4895-bc27-c983a367a9a8` / lock
`sha256:50f9a34602014a44de489eb978c6684706aeff1435733684b2262133fce553ab`；configuration
`3706e919-0153-4aca-aa4c-69ab18960d3c` /
`sha256:12397b16ac8fb7d57a098e8f6203b8533c59d78d3bf11bc0b5d6371282394c6d`。
prepare operation `29cb2549-e72b-40df-bb46-7709a763da4c`，唯一外置 Host PID 96921 自然领取；
verify `eac8f353-1283-44b1-be96-1d1c584b7f76`、configure
`c739041c-d92e-4a20-aa50-aeae8456369c`、enable
`aef9be26-b1e9-4623-8b8d-8d52b0c0881a` 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `48afe673-39fa-49d4-b2ae-7b68c9da7fff`，cutover operation
`d6900aae-ce9e-4334-b440-6a337de63dbc`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `e494b1ad-f79f-40b9-9376-ff38f400b3a5`，resume Receipt
`0c03bd8c-5911-4554-878d-ad0cb33ff71f`；九路全部为 CM extension rev240/group267，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 96921，第二 Host=0、snapshot worker=0、18181=0。以 renewals=3 为 baseline，
38 个只读样本新增 12 次续租，最终 renewals=15、sequence=28；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev181 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `186 passed, 7 warnings`。下一波为 CM saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev182、
recovery60、enable rev183，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。注意上一 attempt 终态为 **rev5**，guard overlay 仍需
predecessor_view revision=4。本提交完成后自动进入该波。
