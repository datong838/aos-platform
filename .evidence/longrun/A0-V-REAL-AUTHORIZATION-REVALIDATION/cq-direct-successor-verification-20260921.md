# CP 正式退休与 CQ direct successor 验证（2026-09-21）

## 结论

`CQ_DIRECT_SUCCESSOR_GREEN`。CP 以唯一 failed attempt **rev4** 的正式终态完成 disable settlement，九路从
rev249/group276 经 fence 收敛到 legacy rev251/group278；CQ 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev252/group279。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `77a1798d`；CP installation `1d8b71c5-1cde-4d16-b16f-835f92bf8663` / generation
`9b0201fc-9822-4527-b63c-23cbd416057d`，definition rev193 disabled，唯一 failed attempt
`4c63e9fd-6f11-461d-a753-87962f5306ad` **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev249/group276、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CP 正式退休

唯一 CP Host PID 6635 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`fc24ee2f-52cb-40e8-98e0-dd260db335d2` succeeded；fence Receipt
`71852b08-047e-462f-b853-674a9f56192f` /
`sha256:43d877cca09b332130d88bd27939f1ea19e3497d4e8ea26e7d0c0b5cee36c79f`，detach Receipt
`4603f48f-2d3a-4581-b837-b85658a2cf50` /
`sha256:05a9ec8c3b477d23c0b329dded09c2d4ad08d686a2997fc36bb4bab46db95205`；
binding rev9/epoch5 disabled，九路 legacy rev251/group278。

## 3/6 CQ lifecycle

CQ installation `fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80` / generation
`ae8a1005-99fb-48c5-9dfe-8f76590bc0c8` / lock
`sha256:6b3debbfebb5b16297f35e2271944a8a9775b2c178922d31525655088f919b50`；configuration
`85103076-e401-4624-8141-4dc8374db731` /
`sha256:f63e3f688081dac051643213f06ab62d0193c60f8e14859f2a510897c891511c`。
prepare operation `2069f6d3-1b40-4f06-9aff-62febe156943`，唯一外置 Host PID 8784 自然领取；
verify `249a6f42-2bc4-4c43-8776-57415a5d0626`、configure
`514257ce-fe7c-436c-8f60-a3b1af0ed534`、enable
`4d2814e6-5ca2-4267-bf91-95316af6642e` 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `89af2eef-21fd-4d1d-916e-5d02b2cbf677` /
`sha256:3a39a4272a4d52c76222100c3f279392bfb37a31c803f56e2762632fe22fd52e`，cutover operation
`ebd2d074-9800-4ccb-9f91-0fed1beda3d1`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `f926beec-032d-4535-be50-7829243ab0f5` /
`sha256:71cf405f976604ba84edb2b9fefe926059aa3e231f413f3a50c4751c2c1279ce`，resume Receipt
`c9e5216d-9040-4c63-b9f7-065c71c8b6c8` /
`sha256:0832a382a39f720c356b9178c8eb5955b3db5b6d31f67692eb80662330a07993`；九路全部为 CQ
extension rev252/group279，claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 8784，第二 Host=0、snapshot worker=0、18181=0。以 renewals=3 为 baseline，
36 个只读样本新增 12 次续租，最终 renewals=15、sequence=28；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev193 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `test_a0v_bn_saved_snapshot_recovery.py`。下一波为 CQ saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev194、
recovery64、enable rev195，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。注意上一 attempt 终态为 **rev4**，guard overlay 仍需
predecessor_view revision=4。本提交完成后自动进入该波。
