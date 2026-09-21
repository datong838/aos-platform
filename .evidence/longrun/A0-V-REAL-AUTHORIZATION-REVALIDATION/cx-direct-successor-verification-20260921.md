# CW 正式退休与 CX direct successor 验证（2026-09-21）

## 结论

`CX_DIRECT_SUCCESSOR_GREEN`。CW 以唯一 failed attempt rev4 完成 disable settlement，九路从
rev270/group297 经 fence 收敛到 legacy rev272/group299；CX 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev273/group300。CX configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `e2b5541a`；CW installation `0d5d5a7f-6e40-4725-b337-b79acc7d896a` / generation
`a60036f1-5887-4157-ad32-616925b547bf`，binding rev6/epoch3，definition rev211 disabled，
唯一 attempt `0f9c30e6-012d-4a08-9aed-f7b0e0492c31` failed rev4。基线为十二 Run/Receipt
与零副作用。

## 2/6 CW 正式退休

Host 32943 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`e69aa8dc-45ab-4d4d-bb23-008fe3491524`，fence `95052a81-eceb-4baa-b4da-5c367bae23b7` /
`sha256:8ed26ae5a2a408d1534365272ed80e093488b88d94d8883ef60e4261bc4eb783`，detach
`5aa372a9-1a82-41ff-b25e-00e898cda82a` /
`sha256:2f121bf22c69efb2e4f37e1df1c17202c5c695e6a378459a92d07054108af78c`；binding
rev9/epoch5，九路 legacy rev272/group299。claimedByHost=false。

## 3/6 CX lifecycle

CX installation `2e374e12-7523-466d-aed7-bdabe8b69aff` / generation
`222870ba-ad3c-4cf5-a6de-e1b3a52ab5bc` / lock
`sha256:479419d261424399c29cac763588440b6ad4981b42bdf67b2a1615d16e715ccc`。prepare
`03652e8e-fb4d-4400-be26-3512ff374418`；verify `d693c6f5-9119-46dd-b65c-1801e459d633`；
configure `c1ec9f92-56b7-49ec-8719-e320d9b3394c`；enable
`91997460-b82c-4999-9153-5746b833ff8c`。configuration `a548862b-ade7-4ff4-8796-54ebbfba6ee4`
rev1/hash `sha256:955f42dcba8aa82a7c097fd661402f8f4c22ebd0f2b8abb753f609673459c1ef`，policyRef
RuntimePolicy rev11。唯一 Host PID 36763，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-cx-successor-v1`，receipt
`03b286b9-7c43-4410-9f0d-2ef6739ffe69` / hash
`sha256:aff6fcc7cdadde4860aa0d8b3d8b9b6b9310fd31ff84f651c8db5923d2fd2a3f`。cutover
`686de66e-fb8f-41c9-ad9d-188bca013a92`；prepare `e51e11eb-636b-4e35-8f44-9db42dc573ff` /
`sha256:312632132162f9cb79ba3604e575bf34dfb1e8a8739bb9ef1b065c540d742bb7`；commit
`82c78646-38b9-4c17-ab28-45930d17822f` /
`sha256:fc755bf801fb67abb5bbda5689c659110dfcb908200ef705853786705fe6918d`；resume
`e83ca10b-7e4e-47b6-9ed5-73209ee29cf5` /
`sha256:c8971f0123bc50e69ddfdb2656aab76c9978acddf200f2956621fe354ca20d3a`。九路
rev273/group300。

## 5/6 唯一 Host 健康观察

Host 36763 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 4，38 samples，
renewals 16/sequence 29，delta +12。binding rev6/epoch3 enabled/ready，attempt=0。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 CX saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
