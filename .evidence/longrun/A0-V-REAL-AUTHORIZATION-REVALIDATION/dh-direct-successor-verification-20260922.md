# DG 正式退休与 DH direct successor 验证（2026-09-22）

## 结论

`DH_DIRECT_SUCCESSOR_GREEN`。DG 以唯一 failed attempt rev4 完成 disable settlement，九路从
rev300/group327 经 fence 收敛到 legacy rev302/group329；DH 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev303/group330。DH configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `4af58ebe`；DG installation `d551d104-f240-4b27-b738-1ef47129b5a4` / generation
`6c1780ab-746b-4303-a9ad-dc30039af8a4`，binding rev6/epoch3，definition rev241 disabled，
唯一 attempt `6e9e2fc8-d598-4e61-a6f0-d265ef7bceed` failed rev4。基线为十二 Run/Receipt
与零副作用。

## 2/6 DG 正式退休

Host 82684 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`1a745c65-7ad2-41ff-ae0a-55427d8462dc`，detach
`6d21f82c-7521-4c36-89c0-06f360339b02` /
`sha256:7bd17d373e1281fbb5768e5b99b839b617d30c89a2e3e088afcb285818129c22`；binding
rev9/epoch5，九路 legacy rev302/group329。claimedByHost=false。退休 preflight 前未创建
`replacement-dh`。

## 3/6 DH lifecycle

DH installation `10d583ad-96ee-4b1a-bb18-92e428abe16e` / generation
`107a24f5-691d-4f2a-9b46-4e7b21938146` / lock
`sha256:aad5193620d1517a9b3be224440004eb040ad4b439d057ea0291ff0724d5d334`。prepare
`4b223bbb-771e-4d94-bd65-c25dd6ae20e4`；configuration `b1a8b55d-e393-4dbb-b416-7dfb2dbe9874`
rev1/hash `sha256:91024b4c4c600019589f868bcc00d904818a0ffce73a34924e678ee7ea8e76f0`，policyRef
RuntimePolicy rev11。唯一 Host PID 86843，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-dh-successor-v1`。cutover
`843181a5-c8be-42e4-953a-9500534058a9`。九路 rev303/group330。

## 5/6 唯一 Host 健康观察

Host 86843 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 2，86 samples，
renewals 14/sequence 27，delta +12。binding rev6/epoch3 enabled/ready，attempt=0。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 DH saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
