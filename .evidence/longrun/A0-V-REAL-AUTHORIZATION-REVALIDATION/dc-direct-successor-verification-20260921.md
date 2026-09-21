# DB 正式退休与 DC direct successor 验证（2026-09-21）

## 结论

`DC_DIRECT_SUCCESSOR_GREEN`。DB 以唯一 failed attempt rev4 完成 disable settlement，九路从
rev285/group312 经 fence 收敛到 legacy rev287/group314；DC 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev288/group315。DC configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `20a301c6`；DB installation `aaaa1ac1-2c35-4c35-8e7b-3ed6cd47f9c8` / generation
`c1ae6205-0743-483c-82e3-1d1c95b1ab31`，binding rev6/epoch3，definition rev226 disabled，
唯一 attempt `1679bef7-84fc-408c-9bb2-d202ba68dc91` failed rev4。基线为十二 Run/Receipt
与零副作用。

## 2/6 DB 正式退休

Host 48103 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`d10cce0c-d412-4e29-95a4-68c010cb2522`，fence `c1d007ee-df26-4914-a4a7-d1a4177ead84` /
`sha256:4d3dd3a76f594688c7ab0ad79e94bed0ec1d7bc41f94b155c22ca861c7cb19ab`，detach
`eceafbf4-d492-43d5-b036-d49e054de133` /
`sha256:4a74a25a361e745a41bddde502105c030399a716d2f5f6f9ed5f01fa36c4aa54`；binding
rev9/epoch5，九路 legacy rev287/group314。claimedByHost=false。退休 preflight 前未创建
`replacement-dc`。

## 3/6 DC lifecycle

DC installation `02d39eb8-174e-432f-9776-57de7c4436c8` / generation
`bd59503f-eb9e-4fe6-a09d-a92a3b924682` / lock
`sha256:4c19a327b9536269eb3582b82814f3342237d8c95bb5c65c29e402d55f86aa4b`。prepare
`66cdef5b-6105-40b1-ab79-7343f38f1438`；verify `e2fc8df0-b9c8-4657-aba5-53935c1f6bbe`；
configure `cf515278-f15f-4575-a14d-464d04587008`；enable
`7ba7fa2b-2246-469b-a1ae-5c42ac5a618d`。configuration `6c04d5a7-5f0c-42b1-84ad-527cd8798cb2`
rev1/hash `sha256:5a2c9823aeb2af8e8c57209022649ed035f2035526ac9a5e8b6375f3847b387e`，policyRef
RuntimePolicy rev11。唯一 Host PID 51083，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-dc-successor-v1`，receipt
`4aa4da7e-b3f0-47d2-8bef-e0150edd7e36` / hash
`sha256:13afc97f89e987a59f2f662aaba362d692ce910ac94a96c236c762a5c0cdb45e`。cutover
`232d8e1e-9efb-4e26-99ce-e83872539a32`；prepare `1674feec-7ec2-46fb-b9ce-eb98153135fa` /
`sha256:c5f83dc74c7b5467bb21c0bd3999e9bc08656cd3c42801129a4f5d926d497d02`；commit
`294aeac4-c872-468c-88f6-9f9e8fbdb402` /
`sha256:6da5065afb43e1ae6c95f5bad39cfebd501d6216680a6ff3e3f6c2ed092c995f`；resume
`28407391-f8ee-49c6-8a12-1c2aabfd47a6` /
`sha256:d405a688ff99f0d531aa7ef24edaa10ccf1a0edee43b04aad371989698cb917b`。九路
rev288/group315。

## 5/6 唯一 Host 健康观察

Host 51083 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 3，36 samples，
renewals 15/sequence 28，delta +12。binding rev6/epoch3 enabled/ready，attempt=0。
CLI 二次 freeze 因 `health-observation-result.json` 已存在而失败；已 inspect 冻结结果，
未重发观察。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 DC saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
