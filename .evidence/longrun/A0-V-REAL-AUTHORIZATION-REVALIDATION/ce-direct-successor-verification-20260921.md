# CD 正式退休与 CE direct successor 验证（2026-09-21）

## 结论

`CE_DIRECT_SUCCESSOR_GREEN`。CD 以唯一 failed attempt 的正式终态完成 disable settlement，九路从
rev213/group240 经 fence rev214/group241 收敛到 legacy rev215/group242；CE 仅凭 exact detach Receipt
创建、启用并 cutover 到 rev216/group243。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `c64538cf`；CD installation `01b41c17-fce2-4bcf-8d9e-a48d2d4bf743` / generation
`22639b06-1211-424d-9f64-696822e0add4`，definition rev157 disabled，唯一 failed attempt
`3eae682d-fddb-4b3b-a7b0-da0eb91152d2` rev4，原因 `RECOVERABLE_EXECUTION_EXCEPTION /
IngressJournalConflict`。基线为九路 rev213/group240、12 members、12 running Run、12 Dataset Receipt，
Store Receipt=0、`ecom_link`=0、projection pending=0、canary=0。

## 2/6 CD 正式退休

唯一 CD Host PID 58751 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`858ed397-2cc6-40dd-b312-3faf129cb0c1` succeeded；fence Receipt
`9820c4ba-ab81-41f2-af30-a3de8379a53c` /
`sha256:a87ea9274e1c76ec37377acef49975ccf1af6b33adaad42a07e5cfde42b6d076`，detach Receipt
`b1d1dc98-268c-484c-a0f6-25502b4e8193` /
`sha256:5f250085b837c6e59cba62e55de38e59785dc06a3ec63c384158aec9148df75d`；binding rev9/epoch5 disabled，
九路 legacy rev215/group242。

## 3/6 CE lifecycle

CE installation `29d1b06d-3baa-4476-9cf8-5ea345d134c7` / generation
`e51d0010-d57f-4f5c-8f7e-7a1d732bebf7` / lock
`sha256:4fce233072671887c694e6c0b6c44080cf67e60407f7a1545b3dc4ef2aac9eb9`；configuration
`adb43db8-401f-4ac0-a372-72c166029550` /
`sha256:ceb54c629cee0180c48ee5bdf9c3e91b0d5d7d1e1ed11fd437f215be4da7cb71`。prepare operation
`706dfb14-3c55-472e-9d69-ea49866727ad`，唯一外置 Host PID 62103 自然领取；首次 verify 在 binding 尚未提交时
只读 fail-closed，未生成结果且未重发 prepare；binding 出现后唯一 verify/configure/enable 均 succeeded，最终
binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `514bc0d7-054e-4615-8a6b-9c0a6f966bc1`，cutover operation
`024169d1-9a17-4530-a745-33aac90053ac`。approve、prepare、pause、commit、validate、resume 全部完成，历史只读
对账状态 resumed；九路全部为 CE extension rev216/group243，claimPaused=false，claimed/unknown/running attempt
均为 0。

## 5/6 健康观察

唯一 Host PID 62103，第二 Host=0、snapshot worker=0、18181=0。以 renewals=3 为正确 baseline，35 个只读样本
新增 12 次续租，最终 renewals=15、sequence=28；attempt=0、running=0、unresolved=0、runtime pending=0、
routes=9、canary=0，definition rev157 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、projection pending=0。
目标回归 `130 passed, 7 warnings`。下一波应为 CE saved-snapshot recovery：纯 HTTP 18181 证明
Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev158、recovery52、enable rev159，关闭端口后启动唯一
自然 worker，观察唯一 attempt 到正式终态，并按既定 fail-closed/1800 秒规则收敛。按用户在本波执行期间的明确
指令，本提交完成后暂停，不在当前轮启动下一波。
