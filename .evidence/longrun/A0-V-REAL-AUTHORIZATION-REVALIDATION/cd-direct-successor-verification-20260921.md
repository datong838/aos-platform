# CC 正式退休与 CD direct successor 验证（2026-09-21）

## 结论

`CD_DIRECT_SUCCESSOR_GREEN`。CC 以唯一 failed attempt 的正式终态完成 disable settlement，九路从
rev210/group237 经 fence rev211/group238 收敛到 legacy rev212/group239；CD 仅凭 exact detach Receipt
创建、启用并 cutover 到 rev213/group240。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与重启基线

HEAD `bd8e4b84`；电脑重启后原 CC Host PID 38020 已不存在，但三项资源仍 pending。方案明确进程消失不等于
资源释放，并冻结 CC installation/generation/lock、definition rev154 disabled、唯一 failed attempt
`74ee33d8-b0d4-444a-9c01-ba31e9358552` rev4、九路 rev210/group237 与全部零副作用边界。

## 2/6 CC 正式退休

首次 preflight 因资源未 released 正确 fail-closed，无写入。definition disabled、attempt terminal、worker=0、
第二 Host=0 下只恢复同一 CC Host owner PID 58524，随后 SIGTERM 正常退出，三资源读回 released=3。
正式 disable operation `9cf43145-2578-4815-9d14-7ac7430c6327` succeeded；fence Receipt
`86790f4d-7dc0-4602-903b-1b45074cde03` / `sha256:020eaf0f7b1d10cc64bd20fa312cd277b54af2be876973a72837e7f79b73c4e2`，
detach Receipt `af7f0b34-1279-4ca7-972b-ef0e31fd53b3` /
`sha256:848870b0fd047ebf70beb0361ba99e9e4b72375138d66b2df8aeda9ee6c11ea3`；binding rev9/epoch5 disabled。

## 3/6 CD lifecycle

CD installation `01b41c17-fce2-4bcf-8d9e-a48d2d4bf743` / generation
`22639b06-1211-424d-9f64-696822e0add4` / lock
`sha256:3c38e9de616a063e451e53f23d0cf5ba08101a7ba0854904107fd5d3293ab65a`；configuration
`2ea2c035-df5e-4eb0-95aa-5283108c873d` /
`sha256:77289a41ae6647d649f429803d87c9f1ffbd3323c1ed89bd7cddf89a0db00c65`。prepare operation
`0450e182-c811-4282-bccc-203a918a9561`，唯一外置 Host PID 58751 自然领取；prepare/verify/configure/enable
均 succeeded，binding 到 rev4/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `265fe7eb-2e18-4b23-8a53-d31cc6dcac06`，cutover operation
`71d85398-64db-4cfe-8df6-b5f83fdc7ebb`。工具 30 秒边界后检测到 phase intent/result 已存在，未重发；历史只读
对账为 resumed，commit/validate/resume Receipt 完整，九路全部为 CD rev213/group240，binding rev6/epoch3 ready。

## 5/6 健康观察

唯一 Host PID 58751，第二 Host=0、snapshot worker=0、18181=0。正确 baseline renewals=4，36 个只读样本新增
12 次续租，最终 renewals=16、sequence=29；attempt=0、running=0、unresolved=0、runtime pending=0、routes=9、
canary=0，definition rev154 disabled。一次误用 sequence=16 作 baseline 的只读观察在未落结果前中止，未产生业务写入。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、projection pending=0。
目标回归 `123 passed, 7 warnings`。下一波自动执行 CD saved-snapshot recovery：纯 HTTP 18181 证明
Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev155、recovery51、enable rev156，关闭端口后启动唯一
自然 worker，观察唯一 attempt 到正式终态，并按既定 fail-closed/1800 秒规则收敛。
