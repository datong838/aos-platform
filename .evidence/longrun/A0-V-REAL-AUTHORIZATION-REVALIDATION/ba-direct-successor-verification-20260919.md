# BA 直系后继验证

## 结论

`BA_DIRECT_SUCCESSOR_GREEN`。BA installation `9110f69b-bb31-4d17-98e8-6c5ed1d9234f`、generation
`197f5036-656a-4b58-a261-e93e2fffea18` 已完成创建、runtime-apply、verify、configure、enable、successor
registration 与六阶段 cutover。最终 Binding rev6/epoch3 ready/enabled/unfenced，九路 extension
rev129/group156，definition rev82 disabled。

## 父权威与单 Host

- 唯一父权威为 AZ disable operation `06849afe-ee19-486d-9d56-5247e947d8ab` 的 detach Receipt
  `ee221609-d3d5-4227-8382-063d2ca0eab2` / hash
  `sha256:36b32dccacc9b7f8e78579fac44db423fe3ab470bc5165e205bf268c4cab8a7c`；前态九路 legacy
  rev128/group155、Binding rev8/epoch4 detached。
- 全程沿用唯一前台 Runtime Host PID 29815，无第二 Host、无 KeepAlive、无 Cron/snapshot worker。
- runtime-verify succeeded 后连续 stage/configure/enable；enable `1eac75bb-79c6-4409-a917-ecbc2db30bd2`
  在 fresh-health 窗口内正式 succeeded，无 accepted-unknown。

## 安装、登记与切换

- BA lock `sha256:6fc165d534435f39488e59c47d615501c1b011beadb59a4a92ed1de76d769757`；configuration
  `2dbe3f41-67b6-4ac6-b84e-b05d01392080` rev1/hash
  `sha256:6902d87b35a0d6d303083abfc29e375a3e3cdd2f38a3123eff1e5c5109608de2`，runtimePolicy rev9。
- runtime-apply `82172075-d9ed-428f-8d5e-f201320aba7f`、verify
  `bdfb6276-6902-439f-977b-374916a2907e`、configure `c82d3056-ce10-40fc-a328-8571d29d29cb`、
  enable `1eac75bb-79c6-4409-a917-ecbc2db30bd2` 均 succeeded。
- registration Receipt `bff6924c-b05a-4f65-be98-9c41eed445fa`，content hash
  `sha256:bde3aea8454edf22012171e5584dc90f60bc5d849220dd3c0a1a98ec4abe80ce`，登记时 executable=false。
- cutover operation `c9f78abb-2df1-450e-be02-11ae0bcc7fcf` 完成 approve/prepare/pause/commit/validate/resume；
  prepare `f2714cc3-3f83-4990-9f41-1cb4ebcc6098`，commit
  `aa3906ef-7af9-496b-81ac-13e6eef30499`，validate `42eda1ec-c884-4489-9653-a1a295bd3309`，resume
  `53309dbc-1f00-42b7-b2f0-93556d401cc3`。最终九路全部指向 BA，claimPaused=false。

## 健康与零副作用边界

- 健康观察从 renewal4 到 renewal16，新增 12 次；runtime-apply event sequence29，三资源保持 pending 且
  observed_release=false，Lease 持续续期。
- BA attempt=0，全租户 running runtime attempt=0、unresolved=0、runtime pending=0、canary=0。
- 十二 saved running Run 与十二 Dataset Receipt 保持；Store Receipt=0、`ecom_link`=0、projection pending=0。
  未启动 Cron/snapshot worker，未手工 `run_definition`，未读商城源数据，230 L0 挂起，未 push。

## 私有证据与回归

- preflight/create `283801db5cd39e6db8284e3a576794f91078c8e759b131e91e2ea987a6572010` /
  `ce05510222eb55ac54eda23a7e792c9604d50a850c8db7218cd628df5f362b52`
- prepare/verify `997469f86db2ba56e4a34d8d4ab475fe920a6d4d0163f06104cc5d2c7cc7d679` /
  `623523d3927a062395cdbe7980dba4ebd7a41ab56c5472d2e75006df4d69ceaa`
- stage/configure/enable `a92be032d9ef6e5d932d87218931dc3157756942344b8118fb3dc9d71aeb4cc1` /
  `62967a51583fa77774bfa0a8aaf209b49b2e9955bdafe546a646bea9a979f6bb` /
  `faed9f55432417c66bb1d626e73c42c7b83eb857be4d4cb14c8b40c3256903f3`
- registration `adca853da453a01243b1a7bb7de48cf6b875e0923755968db81280c88b0114f5`；cutover resume
  `0897ee6ba8895a9664cd69667408ee9b9379b7ff2223415ac5acf4ddadb858ea`；health observation
  `d260bb4d3a35fff93663e97ce244d724fb4f258fddd96bf223d1d997f68f5e2a`。
- BA/AZ 专项回归 `8 passed`；Python 编译与 `git diff --check` 通过。

## 下一波

进入 BA saved-snapshot recovery：plan 先行，纯 HTTP 18181 且 Cron/snapshot worker 关闭；证明唯一 Runtime
Host、第二 Host=0 后再 transfer/recovery/definition enable，最后关闭端口并启动自然 snapshot worker。
