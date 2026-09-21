# CK 正式退休与 CL direct successor 验证（2026-09-21）

## 结论

`CL_DIRECT_SUCCESSOR_GREEN`。CK 以唯一 failed attempt **rev5** 的正式终态完成 disable settlement，九路从
rev234/group261 经 fence 收敛到 legacy rev236/group263；CL 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev237/group264。全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。

## 1/6 plan 与冻结基线

HEAD `4377ea2d`；CK installation `c1cb44ba-68ae-4d32-9974-5f031554fed2` / generation
`1edb1688-e2b6-42f0-b513-849ae372859e`，definition rev178 disabled，唯一 failed attempt
`7c99b249-fc1e-4844-abc5-8b7cc268fd39` **rev5**，原因为
`RECOVERABLE_EXECUTION_EXCEPTION / IngressJournalConflict`。基线为九路 rev234/group261、
12 members、12 running Run、12 Dataset Receipt，Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。

## 2/6 CK 正式退休

唯一 CK Host PID 91080 以 SIGTERM 正常退出。正式 disable operation
`87aa9a73-329e-42df-ac89-0e24bd8e4780` succeeded；fence Receipt
`f6beabd7-7ebf-4365-a869-c846f16b2fb2` /
`sha256:04cef856c856be3a9a0de10e12f98b5354f79852f8019bafacfb82df8acc9065`，detach Receipt
`8ed70360-4e39-4a96-992f-d70f3222b541` /
`sha256:812e9450e64a730d13b34db809903cbd61d3c537c4bc4fb3ba06eb09aaa15144`；
binding rev9/epoch5 disabled，九路 legacy rev236/group263。

## 3/6 CL lifecycle

CL installation `64e49f66-b0ef-4676-91c1-eb05f6d1d0b1` / generation
`a583218d-f65b-4697-9e60-7281a0bff66e` / lock
`sha256:9e4ab375110d6d458b98012872bc35a39545afc7e6d547ed48c57667f4838a8e`；configuration
`49fb289d-e60a-4f88-841e-dd866c901241` /
`sha256:633751d9a47c3829ae084e0ccf45908ef6acdef55bbf042a5754b73a1c2cdf4b`。
prepare operation `1db4380b-64f4-4d65-96e6-349258c57d4a`，唯一外置 Host PID 94133 自然领取；
verify `b46929f7-4a51-4249-918e-d918fbbfd5fb`、configure
`0105579e-8d91-44e9-83df-2d91e82f398e`、enable
`a900330c-e30e-4fee-a55c-3d18a4556033` 均 succeeded，最终 binding rev6/epoch3 enabled/ready。

## 4/6 注册与 cutover

successor registration Receipt `061a790a-268b-4d30-ae62-2801b46b61dc`，cutover operation
`e381a022-f80b-4d45-9e98-91a51077213e`。approve、prepare、pause、commit、validate、resume
全部完成，commit Receipt `f53216b6-3325-45a6-8a79-95c78c761a10`，resume Receipt
`ecc2fe2a-8670-4f24-97d8-c25e0c3df768`；九路全部为 CL extension rev237/group264，
claimPaused=false，claimed/unknown/running attempt 均为 0。

## 5/6 健康观察

唯一 Host PID 94133，第二 Host=0、snapshot worker=0、18181=0。以 renewals=3 为 baseline，
15 个只读样本新增 12 次续租，最终 renewals=15、sequence=28；attempt=0、running=0、
unresolved=0、runtime pending=0、routes=9、canary=0，definition rev178 disabled。

## 6/6 零副作用、测试与下一波

最终 12 members、12 running Run、12 Dataset Receipt；Store Receipt=0、`ecom_link`=0、
projection pending=0。目标回归 `179 passed, 7 warnings`。下一波为 CL saved-snapshot recovery：
纯 HTTP 18181 证明 Cron=false/snapshot worker=false/第二 Host=0；随后 transfer rev179、
recovery59、enable rev180，关闭端口后启动唯一自然 worker，观察唯一 attempt 到正式终态，
并按既定 fail-closed/1800 秒规则收敛。注意上一 attempt 终态为 **rev5**，guard overlay 仍需
predecessor_view revision=4。本提交完成后自动进入该波。
