# CU 正式退休与 CV direct successor 验证（2026-09-21）

## 结论

`CV_DIRECT_SUCCESSOR_GREEN`。CU 以唯一 failed attempt rev5 完成 disable settlement，九路从
rev264/group291 经 fence 收敛到 legacy rev266/group293；CV 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev267/group294。CV configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `1b40478f`；CU installation `2c2d5506-1f80-4557-bf4b-00ead0258002` / generation
`bcaa7ea0-62b1-4238-8615-28db45e3014e`，binding rev6/epoch3，definition rev205 disabled，
唯一 attempt `e845cb50-44dd-489c-a85d-85a8932b4d0f` failed rev5。基线为十二 Run/Receipt
与零副作用。

## 2/6 CU 正式退休

Host 22753 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`2acec273-b5c9-4fc6-8e55-943640f706f4`，fence `9640906d-7bfe-48c0-8b53-951747596187` /
`sha256:3fd39ab5a67fde309e57ffac7db4e9c6a2100aae0f94543fbe13cb5ea17f8374`，detach
`ee918fb3-05db-4ed0-a678-0554225bb427` /
`sha256:bdb72a10abfd3412182543a079b8c4bc813d0c7641186f6558aaa66560eff36e`；binding
rev9/epoch5，九路 legacy rev266/group293。claimedByHost=false。

## 3/6 CV lifecycle

CV installation `f94149ca-a01e-4a20-836f-3f5132e0dbb7` / generation
`82aec2b8-072d-4f2e-9624-f9539c8890a6` / lock
`sha256:9d8d72cdaad153c6e085ead8a3c28c4507fc226b421e0d60be8a100ac38318df`。prepare
`29511d3b-0921-4ce3-9c55-34cbe531f678`；verify `fcfc25c5-a26b-4331-a62b-7a4295337c47`；
configure `5e9146a4-1564-4b68-a8f5-f33ccc29952d`；enable
`cd852573-7d66-422f-b13a-fcf4b3945daf`。configuration `0646dad4-cdf5-4217-a6f2-a566ff2791fe`
rev1/hash `sha256:eada1c5456c0708ff05f7d81b1056d0d00da7441147b1f2bc58bf9d2004a20a4`，policyRef
RuntimePolicy rev11。唯一 Host PID 27622，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-cv-successor-v1`，receipt
`f376cd3a-31be-4f47-a118-3c8bb78a57bd` / hash
`sha256:03db37ec04a57bfd5997df6f75e4820dd23aaf138c1ec66480af1a51f82ac90b`。cutover
`f340ca4e-3cfd-43e7-ad7b-5b548dcf3bc8`；prepare `310b5578-bfc2-4046-9279-fbd593be7cf1` /
`sha256:493d3e2b0547ef6a5521923c114099749a90840c3831ebf754d248b3a7f11b97`；commit
`ab1895ff-9a38-4ffb-ba23-b67ef420ea50` /
`sha256:23d73e86bd5ee365f8392968d928c26b190773b5f4aa91b52dfc8c8ad1cd780c`；resume
`80c8e9c3-709b-4f73-9800-4a3db37d385c` /
`sha256:746edcb4329b1948b6e08cbf9e03715ebbd53cbb03c6e14d8cf2ec09b5da0bd0`。九路
rev267/group294。

## 5/6 唯一 Host 健康观察

Host 27622 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 4，38 samples，
renewals 16/sequence 29，delta +12。binding rev6/epoch3 enabled/ready，attempt=0。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 CV saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
