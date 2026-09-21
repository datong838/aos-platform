# CT 正式退休与 CU direct successor 验证（2026-09-21）

## 结论

`CU_DIRECT_SUCCESSOR_GREEN`。CT 以唯一 failed attempt rev5 完成 disable settlement，九路从
rev261/group288 经 fence 收敛到 legacy rev263/group290；CU 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev264/group291。CU configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `30285b10`；CT installation `b4847c85-b452-4c87-bf56-8a57bc9f8d25` / generation
`0d234db2-8b76-4ec8-a14a-a8c6eec9bbc6`，binding rev6/epoch3，definition rev202 disabled，
唯一 attempt `5b22aca6-70b5-46e0-b5aa-0f477964df96` failed rev5。基线为十二 Run/Receipt
与零副作用。

## 2/6 CT 正式退休

Host 19682 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`4704b467-5d69-4ee3-b4e5-e755c5e98eea`，fence `dcb6fc7e-004e-45e4-a657-b30aaa67ba67` /
`sha256:a84ba705484ee05702d2ceaf50305c3a4e5a289b2f344615f9372e5be146f1ea`，detach
`b1101390-ca5d-43bf-bc6a-c3bc0fc1d4f1` /
`sha256:8809a0a0ff8a8e69291d737a28277a48ef6faea6b8520ae658c55b320ace7123`；binding
rev9/epoch5，九路 legacy rev263/group290。claimedByHost=false。

## 3/6 CU lifecycle

CU installation `2c2d5506-1f80-4557-bf4b-00ead0258002` / generation
`bcaa7ea0-62b1-4238-8615-28db45e3014e` / lock
`sha256:3a1338060d903fc721f71e49b077ac130aa226f64a94e48d09d2ddab16f09200`。prepare
`1bc0569b-be26-4ee5-81d2-631f2ec26885`；verify `7ab391a0-0f11-4996-bca2-a1292d12757b`；
configure `01f6a7c4-f361-4da8-82c4-0cec87a37fcb`；enable
`f8fb690d-665a-42ff-8678-26803cc87408`。configuration `12535ee1-99ae-449c-b3e8-41100a046f58`
rev1/hash `sha256:6aa85c0d8cc9617f96c6e26a4b4b2d06459dbef30af70717274ea6b2b4168cad`，policyRef
RuntimePolicy rev11。唯一 Host PID 22753，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-cu-successor-v1`，receipt
`6e66e9fe-a8d9-4641-aa17-5e3f85c7b640` / hash
`sha256:141568de8dbb78ced4f4ae22d95c6e96d7918465b1a5131e2813965d24dd32ec`。cutover
`ef453252-1d89-4f02-8f3f-3a05c79d6293`；prepare `dda1a71c-5914-4be2-a070-640a6fb946c5` /
`sha256:f0de2e627856ed0f9fe40cafbbf27961a0079df74a162ebdec7411db3e3ca2cb`；commit
`d36c3562-9720-46f7-a4de-3b9f9135783e` /
`sha256:1224a4d926a4295566a2887930678653689b859f56b4adf7c231cc58ef3076af`；resume
`455236c4-62b9-44c8-9a8b-4a41f3df7ac0` /
`sha256:17caa72dbb75825c2014f05c7f6c92fba29bcdda5e6bdd1cbcf96fc480a6fa9b`。九路
rev264/group291。

## 5/6 唯一 Host 健康观察

Host 22753 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 4，36 samples，
renewals 16/sequence 29，delta +12。binding rev6/epoch3 enabled/ready，attempt=0。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 CU saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
