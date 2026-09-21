# CM 正式退休与 CN direct successor 验证（2026-09-21）

## 结论

`CN_DIRECT_SUCCESSOR_GREEN`。CM 以唯一 failed attempt **rev4** 的正式终态完成 disable settlement，九路从
rev240/group267 经 fence 收敛到 legacy rev242/group269；CN 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev243/group270。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `8eaddfb2`；CM installation `b52c8e1c-a343-4ef4-b106-38d859ba9677` / generation
`d3ec88cc-a05a-4895-bc27-c983a367a9a8`，definition rev184 disabled，唯一 failed attempt
`da4fed10-4cdc-4147-8595-d2f40c568419` **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev240/group267、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CM 正式退休

唯一 CM Host PID 96921 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`cc32921f-27a2-43a0-94e4-23b84992e278` succeeded；fence Receipt
`4bbcd74b-4a66-4cbb-8b24-4197cfbd86a9` /
`sha256:a93154dbee0d45c24a6f43485cdfa4df2b038ac154a0c600e7a9d7fdff7f41c1`，detach Receipt
`a118ae49-92de-477a-92f3-0d855c48a472` /
`sha256:5074648fad39e4be7040cac99fc18cc0748a6d162e2700ea0d78aa19c80803af`；
binding rev9/epoch5 disabled，九路 legacy rev242/group269。

## 3/6 CN lifecycle

CN installation `1366f4dd-47d9-42c1-b26a-759c7bd556da` / generation
`cd0601e0-2668-496d-9f93-561d2e69a170` / lock
`sha256:18045e8ebd31484b42a6ae4cebb9eb81b5d56be02b3a5929405ad2957f0c96bb`；configuration
`6b8a4673-8eef-487d-9bc6-a139b3b311ed` /
`sha256:d371bf7e45252e48e9a4174d67eea55d0a43e7e7dad1b039ce500b3c0cbad4b8`。
prepare operation `4ba3f9c1-7480-48f5-ab79-e4f167968012`，唯一外置 Host PID 519 自然领取；
verify `01b4427e-c1cd-46e9-a7eb-6d391a2e0544`、configure
`0d89d2b2-28c3-46e1-ad20-d5c8f03a8805`、enable
`85427ebb-cfc2-4e7a-b70a-e86d27f893a0` 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `b54b15a1-01aa-496d-a019-e55863b2a5c5`，cutover operation
`abfafc4b-9a00-433e-af6c-54636f8e5983`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `84df37c6-7916-421d-b196-d77e29512855`，resume Receipt
`7c43ad4a-47e3-4daa-a7d1-b59e661569ed`；九路全部为 CN extension rev243/group270，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 519，第二 Host=0、snapshot worker=0、18181=0。以 renewals=3 为 baseline，
38 个只读样本新增 12 次续租，最终 renewals=15、sequence=28；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev184 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `193 passed, 7 warnings`。下一波为 CN saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev185、
recovery61、enable rev186，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。注意上一 attempt 终态为 **rev4**，guard overlay 仍需
predecessor_view revision=4。本提交完成后自动进入该波。
