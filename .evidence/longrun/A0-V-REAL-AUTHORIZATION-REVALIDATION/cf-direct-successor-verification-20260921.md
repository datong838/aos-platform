# CE 正式退休与 CF direct successor 验证（2026-09-21）

## 结论

`CF_DIRECT_SUCCESSOR_GREEN`。CE 以唯一 failed attempt 的正式终态完成 disable settlement，九路从
rev216/group243 经 fence 收敛到 legacy rev218/group245；CF 仅凭 exact detach Receipt
创建、启用并 cutover 到 rev219/group246。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `09335f8b`；CE installation `29d1b06d-3baa-4476-9cf8-5ea345d134c7` / generation
`e51d0010-d57f-4f5c-8f7e-7a1d732bebf7`，definition rev160 disabled，唯一 failed attempt
`c1b948a7-faf2-4b92-8e8d-1f9d66b51201` rev4，原因 `RECOVERABLE_EXECUTION_EXCEPTION /
IngressJournalConflict`。基线为九路 rev216/group243、12 members、12 running Run、12 Dataset Receipt，
Store Receipt=0、`ecom_link`=0、projection pending=0、canary=0。

## 2/6 CE 正式退休

唯一 CE Host PID 62103 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`077d774d-7614-4270-ad29-7f90871c3e9f` succeeded；fence Receipt
`86ca228f-8ff8-4c1e-82a0-686a2be54952` /
`sha256:72d7ed3fbdf8691f42215acb80225b9fa9e1c0e3d3dae02291799e38c31e5244`，detach Receipt
`d626046d-ceae-402e-8fbe-51ebe87b1409` /
`sha256:ffa929f43cc570edf7029abec398fe03c52cd06b4d3fd8fdb7a0a7fd5ede3981`；binding rev9/epoch5 disabled，
九路 legacy rev218/group245。

## 3/6 CF lifecycle

CF installation `8cf0c597-cf81-4fa5-b1ff-f27e3537a94c` / generation
`88996259-ad79-4aa6-962c-c29a24559db8` / lock
`sha256:672e44b9964c3d284028abd6af01fdbc6e2eeb81fa732e68a88061d28331a214`；configuration
`13d3db4e-df8a-46c9-95c1-5a84ba01b896` /
`sha256:5e0b8d605a52f970f887ba60c60b73392962555b53d44564e017af6aae37d0e1`。prepare operation
`f8c49bee-1e87-4d64-be32-e683e84dbb59`，唯一外置 Host PID 73889 自然领取；唯一 verify/configure/enable
均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `5cfc6d1e-13f8-4d6d-bf0f-835e33b23ed2`，cutover operation
`41853ebd-b68f-4db6-aeda-ac9c765be324`。approve、prepare、pause、commit、validate、resume 全部完成，历史只读
对账状态 resumed；九路全部为 CF extension rev219/group246，claimPaused=false，claimed/unknown/running attempt
均为 0。

## 5/6 健康观察

唯一 Host PID 73889，第二 Host=0、snapshot worker=0、18181=0。以 renewals=4 为正确 baseline，36 个只读样本
新增 12 次续租，最终 renewals=16、sequence=29；attempt=0、running=0、unresolved=0、runtime pending=0、
routes=9、canary=0，definition rev160 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、projection pending=0。
目标回归 `137 passed, 7 warnings`。下一波为 CF saved-snapshot recovery：纯 HTTP 18181 证明
Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev161、recovery53、enable rev162，关闭端口后启动唯一
自然 worker，观察唯一 attempt 到正式终态，并按既定 fail-closed/1800 秒规则收敛。本提交完成后自动进入该波。
