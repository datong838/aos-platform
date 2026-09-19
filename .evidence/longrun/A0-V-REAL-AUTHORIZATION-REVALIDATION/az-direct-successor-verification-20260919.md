# AZ 直系后继验证

## 结论

`AZ_DIRECT_SUCCESSOR_GREEN`。AZ installation `40eee6d9-fb03-4657-a83e-aeb38ec4aeeb`、generation
`7b6befaa-2f92-4e62-85f9-0ca060ec4b90` 已完成创建、runtime-apply、verify、configure、enable、successor
registration 与六阶段 cutover。最终 Binding rev6/epoch3 ready/enabled/unfenced，九路 extension
rev126/group153，definition rev79 disabled。

## 双父权威与 Host 修正

- 路由父权威仍为 AX detach Receipt `622c8e25-ec0f-40dd-bf1f-ea57d180a800` / hash
  `sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870`，legacy rev125/group152。
- 失败叶 AY 必须已由 configured-unactivated Receipt `48fc0e55-578d-46ae-b45a-bf8ab8085823` / hash
  `sha256:21494a12aed250565b7f65cf4b8da0a36a5d9d9c8c9cbb433bd2346734df4409` 退休。preflight 同时锁定两者，
  AZ 没有复用 AY identity。
- 旧 `com.aos.a0v-runtime-u` KeepAlive 已 bootout；启动前 Runtime Host=0。本波只启动 PID29815 的单个前台 Host，
  使用 AZ 独立状态文件，无第二 Host、无自动重启守护。
- 针对 AY 的 `HealthObservationStale`，本波在 runtime-verify succeeded 后连续执行 stage/configure/enable。
  enable `25554e86-f81f-488d-90fd-c176f72a8a07` 在 deadline 内正式 succeeded，没有 accepted-unknown。

## 安装、登记与切换

- lock hash `sha256:7826b7400df634c9ad5f538b7db24026fc8930ee4bf6627b5d13277b2fa6afc5`；configuration
  `643a2461-6481-48bf-8f17-df2e8789d169` rev1/hash
  `sha256:8564b723a3d6e3f62f7f6f8095c6d17081283764fce549b2b549b6239e0ef49b`，current runtimePolicy rev9。
- runtime-apply `e56b9d90-1396-4fa4-9c5c-3e7cc0f204b1`、verify
  `83ea0ff2-4365-497d-80ae-23d285be8371`、configure `85ccb627-58e4-4223-a2a2-6bb011fb055d`、enable
  `25554e86-f81f-488d-90fd-c176f72a8a07` 均 succeeded。
- registration Receipt `b2abbe46-af38-4363-b2bb-650d04bb9bfa`，content hash
  `sha256:d73913351e6851c6929c3888db060ad558875f4174c838ae164d5935e4520981`，登记时 executable=false。
- cutover operation `f411835c-ea85-4996-9c64-715e9d04fc35` 完成 approve/prepare/pause/commit/validate/resume；
  prepare `74f80144-dc27-409d-8493-0223c0c69d3f`，commit
  `4b61d95a-f921-41dd-bdb1-b1511bda7772`，validate `0cfc1c91-9e31-4914-acac-457353dc9f8f`，resume
  `da32762c-e74d-4e98-8567-2bd81d774130`。最终九路全部指向 AZ，claimPaused=false。

## 健康与零副作用边界

健康观察从 renewal4 到 renewal16，新增 12 次；最终 runtime-apply event sequence29，三资源保持 pending且
observed_release=false，租约持续续期。AZ attempt=0，全租户 running runtime attempt=0、unresolved=0、runtime
pending=0、canary=0。

12 个 saved running Run 与 12 个 Dataset Receipt 保持；Store Receipt=0、`ecom_link`=0、projection pending=0。
未启动 Cron/snapshot worker，未手工 `run_definition`，未读商城源数据，230 L0 挂起，未 push。

## 私有证据与回归

- preflight `cec6a62762a1f2ea72c9c1ca81df645eb67a8333917ea6042c2c150178dff0b0`
- create `98b316175f5f460386547bc964d9b581de665783857f70309a13fc43891dbb24`
- prepare/verify `9b0062f1951b1cf37a8658ac6b5e827dc32a3e3c1e5918caa65b14280c341b4b` /
  `35f3ee8f46ee53cdc1dbd1bff4a59be3e3b78c67a2d7e7bf773bc3e89bb9ab3e`
- stage/configure/enable `09daf22eeeec351748a975b9122989a29b5d92654a630ac402582266458e871d` /
  `233aba4713625e2b1c7d8d99c730f6c3e5e55d8ada776399055c10f4a18a1e23` /
  `492a9f031476f37486b21d686106dd72f6f12bdbc4264cf88d79932cc7fab76b`
- registration `1e3bd1734fae477c7ebddf34540114f3bcc4c21351a0665c41ddf9f032ca435b`
- cutover resume `4983f14aeec012f3a1e27856ca32cab448137fbcdd2774807104af8ef09b29a9`
- health observation `c315c4e97ce35c3cb85341a4f94c7ace8fe9df338980c00fbd27d333e40b5c71`
- AZ/AY 专项回归 `7 passed`；Python 编译和 `git diff --check` 通过。

下一波进入 AZ saved-snapshot recovery：plan 先行，纯 HTTP 18181 且 Cron/snapshot worker 关闭；只读证明唯一
Runtime Host、第二 Host=0 后再 transfer/recovery/definition enable，最后关闭端口并启动自然 snapshot worker。
