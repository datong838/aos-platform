# CV 正式退休与 CW direct successor 验证（2026-09-21）

## 结论

`CW_DIRECT_SUCCESSOR_GREEN`。CV 以唯一 failed attempt rev4 完成 disable settlement，九路从
rev267/group294 经 fence 收敛到 legacy rev269/group296；CW 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev270/group297。CW configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `6c4c02cb`；CV installation `f94149ca-a01e-4a20-836f-3f5132e0dbb7` / generation
`82aec2b8-072d-4f2e-9624-f9539c8890a6`，binding rev6/epoch3，definition rev208 disabled，
唯一 attempt `88c9a09f-e5f3-4c65-9f5c-dc35cc1252e6` failed rev4。基线为十二 Run/Receipt
与零副作用。

## 2/6 CV 正式退休

Host 27622 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`17648f28-66dc-4c11-87d2-c32e3a016bcb`，fence `3b93b871-f51f-4dd9-a87f-3acd7ed321fd` /
`sha256:608fd36eca7ec1dd86c78b623425c4625b11a906c1a52e037c072cd305cf946d`，detach
`9add3bab-81be-417d-ab80-18f254ecf43f` /
`sha256:a8bc901472293b85f1b6085e97ea673dbe3ea79216668d6b6c15ffb6a0fb9bea`；binding
rev9/epoch5，九路 legacy rev269/group296。claimedByHost=false。

## 3/6 CW lifecycle

CW installation `0d5d5a7f-6e40-4725-b337-b79acc7d896a` / generation
`a60036f1-5887-4157-ad32-616925b547bf` / lock
`sha256:ed07dc19c26651fd6c845702f96f3a881642361f29d2f6495052a230d1fa0162`。prepare
`65d2b402-68f8-4294-b42c-5585894c6e57`；verify `5c7d4cf1-c231-4ca8-8c0b-050d8c563410`；
configure `a19608d0-7d63-4d8d-b1bf-c103793c5ea9`；enable
`03c5a9bc-3462-41fb-9088-133755517507`。configuration `3c8f431a-36fc-429c-aa4e-36f5a57a19b6`
rev1/hash `sha256:5ba80fe04373371fb8d46773eebf265fb9f325a5e6b91fbf5f458f76bda9653a`，policyRef
RuntimePolicy rev11。唯一 Host PID 32943，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-cw-successor-v1`，receipt
`12b11020-154e-4ca3-b216-860051e33181` / hash
`sha256:1df7fae3017b5295a04e9b47ad38839464894d5f590cc243e7b6133fe2632400`。cutover
`502876a9-ba7c-439d-83ad-e1124cc7e231`；prepare `4fd173ee-e4c7-450e-a470-e531b1d21e8b` /
`sha256:03cdf5cb95afc7a0254e277077c3eb8824cded538217f641daebd8d8359b52ce`；commit
`8a1fa8b0-bf5a-498e-b4cb-280ba369da5f` /
`sha256:d353eeb161359805c2fcc26197efa9b914c15ad93db66470113e7bdc35f5a3d2`；resume
`29085277-daa3-4e6f-95cb-c0f7b27ed55f` /
`sha256:cbf6d791d8e80a99b8ac5ca9d4f5f9be45067fb846abb5a8055090afe59b39ea`。九路
rev270/group297。

## 5/6 唯一 Host 健康观察

Host 32943 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 4，38 samples，
renewals 16/sequence 29，delta +12。binding rev6/epoch3 enabled/ready，attempt=0。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 CW saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
