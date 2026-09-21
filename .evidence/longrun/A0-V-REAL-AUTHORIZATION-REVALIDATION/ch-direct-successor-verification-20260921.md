# CG 正式退休与 CH direct successor 验证（2026-09-21）

## 结论

`CH_DIRECT_SUCCESSOR_GREEN`。CG 以唯一 failed attempt 的正式终态完成 disable settlement，九路从
rev222/group249 经 fence 收敛到 legacy rev224/group251；CH 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev225/group252。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `680286f1`；CG installation `8f42819c-0fc7-48cf-a5c4-9ba96894a6f5` / generation
`3ed300fa-5fff-4949-9fb0-1926412e51ae`，definition rev166 disabled，唯一 failed attempt
`f7b2fc7f-9bce-4102-8f5b-48ec8879ae55` rev4，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev222/group249、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CG 正式退休

唯一 CG Host PID 77505 以 SIGTERM 正常退出，三项资源读回 released=3。正式 disable operation
`bd5e0164-fefb-4751-a7bd-5019a20dd3b5` succeeded；fence Receipt
`23ca4e26-a88e-459e-a439-f8b40e316d74` /
`sha256:02db197c27bcfe08b1a20c0d2ae2811e1394960654501a7bcb2fcf27bd489299`，detach Receipt
`3d65b065-8ad4-4a97-983f-f14ca0ada8cb` /
`sha256:bbf8fb158183e1821129384611658468d0a6d28838068c6ad45960b2b36dc025`；
binding rev9/epoch5 disabled，九路 legacy rev224/group251。

## 3/6 CH lifecycle

CH installation `990f96f7-764e-4002-b691-fc5eb8d4335c` / generation
`0521ccf8-304a-45b3-b820-dc6ebd64b51b` / lock
`sha256:0a550a6efdbd48ea06b35f7559d83b6840dfaae117b6bfd6fa9dbf46733c9ea6`；configuration
`e37e8c76-c50e-467a-8c69-4679b11fdeb7` /
`sha256:ad7a86bb06752105da203133049e3cf0ab9a059f5a569684562aca0d6b96ca35`。
prepare operation `efed6af4-3243-47fd-83ef-8d870cddc3ea`，唯一外置 Host PID 83095 自然领取；
唯一 verify/configure/enable 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `09531cc2-7295-47df-b805-7eb9cc4a67e2`，cutover operation
`c0f54fd5-dcc3-4c4e-873c-e06518620b2b`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `96b2bb9d-17cc-46a6-9e46-cd26428ee97b`，resume Receipt
`8c2df43f-90e8-43e2-8a67-2b99c94d51af`；九路全部为 CH extension rev225/group252，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 83095，第二 Host=0、snapshot worker=0、18181=0。以 renewals=3 为 baseline，
36 个只读样本新增 12 次续租，最终 renewals=15、sequence=28；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev166 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `151 passed, 7 warnings`。下一波为 CH saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev167、
recovery55、enable rev168，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。本提交完成后自动进入该波。
