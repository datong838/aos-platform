# CN 正式退休与 CO direct successor 验证（2026-09-21）

## 结论

`CO_DIRECT_SUCCESSOR_GREEN`。CN 以唯一 failed attempt **rev5** 的正式终态完成 disable settlement，九路从
rev243/group270 经 fence 收敛到 legacy rev245/group272；CO 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev246/group273。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `a992429b`；CN installation `1366f4dd-47d9-42c1-b26a-759c7bd556da` / generation
`cd0601e0-2668-496d-9f93-561d2e69a170`，definition rev187 disabled，唯一 failed attempt
`1cf52d77-baa9-49a5-9315-d705b864c8a0` **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev243/group270、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CN 正式退休

唯一 CN Host PID 519 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`993d8b13-fcf5-4a14-9410-b601d6f7a891` succeeded；fence Receipt
`54a8c390-032e-48f7-930d-5c162d3e156d` /
`sha256:d30e0b8e07028e3a5f9a1846d7dab60b91e2b66d301b842dd0abe2048f8c752e`，detach Receipt
`5f72b40e-543f-49e6-947c-a636a41cee99` /
`sha256:46f951422c2f99c4cc63103b202ae83c8b04bff574282204f5f89f90d3fff09c`；
binding rev9/epoch5 disabled，九路 legacy rev245/group272。

## 3/6 CO lifecycle

CO installation `648b267b-bb8f-4582-ab29-288279f534c7` / generation
`db428c1b-2fe4-4869-8a69-ddffaa909ba7` / lock
`sha256:c0181c85dff7f0989c5f64652814065b6f273b2f31e349044dc125bd7bc486e9`；configuration
`a757203c-099d-4e83-afcd-fe3f12503956` /
`sha256:e9b939576d05c2140d8e5aec574a8d21d052841251838d664e3c18b849d9e1dd`。
prepare operation `d05101eb-707f-45b2-84f8-f43a5c80d69c`，唯一外置 Host PID 4016 自然领取；
verify `a9e4dd3a-79c3-4a89-bf06-3a409120fb44`、configure
`0b50f716-dce5-4440-b441-55eda0cfa336`、enable
`9044ab88-5707-48e5-a8b7-e3bfc97f4879` 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `5aa053e8-635c-42ef-95f0-547fbc54b320`，cutover operation
`7e21a322-9f77-4d5b-baa2-f6d7ba19da13`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `51a180ab-4023-46bf-989f-53602081689c`，resume Receipt
`07e134d9-99ad-4ba3-afaa-a49aed92efe1`；九路全部为 CO extension rev246/group273，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 4016，第二 Host=0、snapshot worker=0、18181=0。以 renewals=6 为 baseline，
37 个只读样本新增 12 次续租，最终 renewals=18、sequence=31；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev187 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `200 passed, 7 warnings`。下一波为 CO
saved-snapshot recovery：纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；
随后 transfer rev188、recovery62、enable rev189，关闭端口后启动唯一自然 worker，观察唯一
attempt 到正式终态，并按既定 fail-closed/1800 秒规则收敛。注意上一 attempt 终态为 **rev5**，
guard overlay 仍需 predecessor_view revision=4。本提交完成后自动进入该波。
