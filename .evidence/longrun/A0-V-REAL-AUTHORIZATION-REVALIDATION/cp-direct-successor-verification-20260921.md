# CO 正式退休与 CP direct successor 验证（2026-09-21）

## 结论

`CP_DIRECT_SUCCESSOR_GREEN`。CO 以唯一 failed attempt **rev4** 的正式终态完成 disable settlement，九路从
rev246/group273 经 fence 收敛到 legacy rev248/group275；CP 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev249/group276。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `1a70ce1a`；CO installation `648b267b-bb8f-4582-ab29-288279f534c7` / generation
`db428c1b-2fe4-4869-8a69-ddffaa909ba7`，definition rev190 disabled，唯一 failed attempt
`f3061da8-baee-4b3a-8307-88d835d42cca` **rev4**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev246/group273、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CO 正式退休

唯一 CO Host PID 4016 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`25fa94bf-b376-4c44-9ce9-147dc89c96d3` succeeded；fence Receipt
`17712e8e-2595-4131-952f-7dd3d8f10f06` /
`sha256:80841a3098ddfcf0c787825d0e8474a92105057b2d00f58eb9c052c65de31aec`，detach Receipt
`d392b12f-9523-487e-aa9c-f473450e95cf` /
`sha256:cccb32032a1403cfd5e5da25875f026330e2f95f743c6d78ba669f9ab576db96`；
binding rev9/epoch5 disabled，九路 legacy rev248/group275。

## 3/6 CP lifecycle

CP installation `1d8b71c5-1cde-4d16-b16f-835f92bf8663` / generation
`9b0201fc-9822-4527-b63c-23cbd416057d` / lock
`sha256:9eb345e2ed64ed8ea82b997218fc6a029a05c342c3e3fba58d85e55b6acf857e`；configuration
`d9e814b2-8a21-4db6-997a-0a3a8139dfef` /
`sha256:76f9707c8fb3edc71c26e3aa2ac6029bd5467101d293114b7abc2e11a232a8a8`。
prepare operation `ca822e5b-c389-4609-8ca7-4dcdcb7c016c`，唯一外置 Host PID 6635 自然领取；
verify `eb9fdb76-a502-4dbc-bdbb-f11530e40ad2`、configure
`61a23107-111c-4477-9610-a205bf44ff20`、enable
`4d74db96-d697-4d22-bd93-6a3debe54658` 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `2cbdcade-6b06-4140-8428-9b8e70d59829`，cutover operation
`ec6199e0-1a5f-4d63-a44b-bd1e8cfe69bd`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `003df33d-3b55-418f-91f2-b80d340564c2`，resume Receipt
`674ae692-1891-429a-8020-b5a5b50d0bd7`；九路全部为 CP extension rev249/group276，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 6635，第二 Host=0、snapshot worker=0、18181=0。以 renewals=2 为 baseline，
36 个只读样本新增 12 次续租，最终 renewals=14、sequence=27；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev190 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `207 passed, 7 warnings`。下一波为 CP saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev191、
recovery63、enable rev192，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。注意上一 attempt 终态为 **rev4**，guard overlay 仍需
predecessor_view revision=4。本提交完成后自动进入该波。
