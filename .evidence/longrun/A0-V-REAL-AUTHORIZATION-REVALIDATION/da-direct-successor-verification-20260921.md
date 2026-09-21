# CZ 正式退休与 DA direct successor 验证（2026-09-21）

## 结论

`DA_DIRECT_SUCCESSOR_GREEN`。CZ 以唯一 failed attempt rev4 完成 disable settlement，九路从
rev279/group306 经 fence 收敛到 legacy rev281/group308；DA 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev282/group309。DA configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `49bc9dc1`；CZ installation `162e4c29-a24e-4c6b-8da7-9582d090d708` / generation
`d1b0f7eb-9677-4d52-a656-a4ae28942976`，binding rev6/epoch3，definition rev220 disabled，
唯一 attempt `d5ca4825-decb-4263-ac0f-f87d2fe8a7b0` failed rev4。基线为十二 Run/Receipt
与零副作用。

## 2/6 CZ 正式退休

Host 43186 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`00211d70-345e-4f90-8d06-81a9a19a4436`，fence `75bbad84-5166-4355-83fe-fb6b679d25ac` /
`sha256:d4e0b0e828ee44f6b5549ffa61a6746e43d934aeecf5af36b1c06f8cf046c389`，detach
`211b6762-550a-475f-aab6-9f6086786787` /
`sha256:de79f4af293f2a159d0ac76ef47392761946cf2fb6d7203b8e89143e2b4b65b7`；binding
rev9/epoch5，九路 legacy rev281/group308。claimedByHost=false。退休 preflight 前未创建
`replacement-da`。

## 3/6 DA lifecycle

DA installation `f4fcdf0b-a37b-419c-9de0-14b08cd7320d` / generation
`dbcdd8cb-c6f4-47cc-91f9-1662f54044c0` / lock
`sha256:47e3295d76f176a553f224b23e550b403be071c96b078d0c0410cd2117b3b38e`。prepare
`e00139ad-ae87-4047-8184-626e93d27b4f`；verify `8a4cd532-29d0-4167-b0b6-5d3a21bc98c4`；
configure `d028e781-4d34-4e4f-9cfc-df68e92a5d59`；enable
`02d31661-b976-462a-bad8-16cabfbe39f1`。configuration `2e78ce65-72a2-4815-a81c-01e2977f3cae`
rev1/hash `sha256:75bae53fe4f7f21f8d416007cc5c21987b14a6e9b2977730a830afe4d95d6977`，policyRef
RuntimePolicy rev11。唯一 Host PID 45786，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-da-successor-v1`，receipt
`9a032a75-afe4-4d47-883c-8630b23789db` / hash
`sha256:4ce268ba6d92c0f1bab6cb54492868a130b442079d10d3a20a26de5e8a32cb65`。cutover
`96e377b4-e6a2-4a2b-be35-9e8a3fa054ce`；prepare `047158d9-9685-4f40-87ef-83ec51e4392d` /
`sha256:23f47d13a18c54ba4d2102eba7299ec58eb3826549b3a7e4c7235f16d93e84a3`；commit
`977ca06b-3975-4662-837d-120a953fe9b6` /
`sha256:e376f8f1c47148e9f0a32954639d56460bcddc8197192691692d612f63b123b7`；resume
`3b3b0c41-75d1-4afe-a4e7-03141b690487` /
`sha256:57e2f9f2c4d13eb4d90b6199df56bcdd50aa80f0612ce136ab0f70d920482c6f`。九路
rev282/group309。

## 5/6 唯一 Host 健康观察

Host 45786 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 4，HEALTH_SAMPLES
samples，renewals HEALTH_RENEWALS/sequence HEALTH_SEQUENCE，delta +12。binding rev6/epoch3
enabled/ready，attempt=0。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 DA saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
