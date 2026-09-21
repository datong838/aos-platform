# CY 正式退休与 CZ direct successor 验证（2026-09-21）

## 结论

`CZ_DIRECT_SUCCESSOR_GREEN`。CY 以唯一 failed attempt rev4 完成 disable settlement，九路从
rev276/group303 经 fence 收敛到 legacy rev278/group305；CZ 仅凭 exact detach Receipt 创建、
启用并 cutover 到 rev279/group306。CZ configuration 直接引用 current RuntimePolicy rev11。
全程未读取商城源数据、未调用 `run_definition`、未重发未知结果。本波无页面改动，未开浏览器。

## 1/6 plan 与冻结基线

HEAD `3bcbb4eb`；CY installation `917cd341-96a5-4428-9508-03c716c587ad` / generation
`a2fdbdb1-430c-417b-969d-6bd30874d38c`，binding rev6/epoch3，definition rev217 disabled，
唯一 attempt `35c2b886-7d38-4ca7-9db6-3f90815420a2` failed rev4。基线为十二 Run/Receipt
与零副作用。

## 2/6 CY 正式退休

Host 39950 SIGTERM 后 binding rev7/epoch4、三资源 released。disable
`40cd6259-298f-4aeb-96b1-3ef1cbe50d6e`，fence `5ae8479a-4402-4762-8df3-fd5d5412ae16` /
`sha256:8d2ac7fc02ef999e2ded94ac48dbb3778722a39c76de2a10cdec632cea86cf56`，detach
`90718b50-d3c8-4712-91c7-41b6ab0358bf` /
`sha256:932ac829528ff8fa7da0d05239f70eee127df1f7e34e7da4a9d6b44d20899b03`；binding
rev9/epoch5，九路 legacy rev278/group305。claimedByHost=false。

## 3/6 CZ lifecycle

CZ installation `162e4c29-a24e-4c6b-8da7-9582d090d708` / generation
`d1b0f7eb-9677-4d52-a656-a4ae28942976` / lock
`sha256:b7045d4fb19c9f0482ac08a12cae8276c4878b3cb2290bd3f4ade0b5b7f885e6`。prepare
`b8bbb317-8b55-4fd4-994c-6a3ae33ccd65`；verify `b27d34d1-c68e-4a1f-8794-433d7c2c5623`；
configure `cdd8bd23-6464-4df5-94f0-3e1f9afdad48`；enable
`13eed36f-d854-4198-8a86-985d0fed1727`。configuration `e6c3bb08-906b-4f88-a5ae-6ee372a5afbb`
rev1/hash `sha256:56f4cb520a135b69bad565b20b17648b17f0d5e1e727150be0a0c2066b8ca03e`，policyRef
RuntimePolicy rev11。唯一 Host PID 43186，credentials BM，bundles BN canonical。

## 4/6 注册与 cutover

注册 KEY `a0v-qyh-clean-generation-cz-successor-v1`，receipt
`c74bb481-9c07-4a38-a26e-d2431d20d266` / hash
`sha256:52bced64eca95b0ea9cb8ab2b1edb159fbd75d25c5a4fa5030c7bb5043172931`。cutover
`3b1ab629-3d48-4ae0-b685-f0dca64ae8cc`；prepare `e0096e67-aae4-4053-b1b3-a591b98bc62d` /
`sha256:2655486edd6c8cfc0e829419a12bc209a32cb32d4802e1cf48b4361c391e5a4e`；commit
`1c47e3b9-db10-4db7-b15b-d175a0d0ac88` /
`sha256:b1ca98ffd5da1b5cfb6e8835a9b6ecaf107b099695fb958d58cc9421abcae4ae`；resume
`656795ac-ad12-4143-a244-4fab25a16e11` /
`sha256:1e4237174fb31fa640b4e25c7ff38e369cbdde7fdf65615a5afa245b16dbaa9d`。九路
rev279/group306。

## 5/6 唯一 Host 健康观察

Host 43186 全程唯一；第二 Host=0、18181=0、snapshot worker=0。health baseline 3，37 samples，
renewals 15/sequence 28，delta +12。binding rev6/epoch3 enabled/ready，attempt=0。

## 6/6 终态、零副作用与下一波

12 members、12 running Run、12 Dataset Receipt、Store Receipt=0、`ecom_link`=0、
projection pending=0、canary=0。本提交完成后自动进入 CZ saved-snapshot recovery。
不使用定时 wake。本波无页面改动。
