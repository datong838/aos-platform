# BG 直系后继验证

## 结论

`BG_DIRECT_SUCCESSOR_GREEN`。BG installation `c52ab6db-176e-4378-ac88-2ee1bfc58487`、generation
`477c3f92-06f0-4dae-9445-ce6d09c3f462` 已完成创建、runtime-apply、verify、configure、enable、successor
registration 与六阶段 cutover。最终 Binding rev6/epoch3 ready/enabled/unfenced，九路 extension
rev147/group174，definition rev100 disabled。

## 父权威与单 Host

- 唯一父权威为 BF disable operation `da0a2b14-f0f7-4f21-8513-c56bf4fbeb29` 的 detach Receipt
  `03852ebe-20e0-4a41-a5fc-c9eb3aa927dd` / hash
  `sha256:ff354c79889453d270baa1b722abdb8785493f7f9432aa42fbe5b6ac7a61c925`；前态九路 legacy
  rev146/group173、Binding rev8/epoch4 detached。
- 全程沿用唯一前台 Runtime Host PID 29815，无第二 Host、无 KeepAlive、无 Cron/snapshot worker；18181 无监听。
- runtime-apply succeeded 后才执行唯一 verify；enable `34f328e9-c77b-4a88-b830-26530c4a941e`
  在 fresh-health 窗口内正式 succeeded，无前置拒绝、无 accepted-unknown、无重发。

## 安装、登记与切换

- BG lock `sha256:0e1880beeac4b28399b828c79b387c32e0be1cc41e982f786a8ddd8d04f88eb3`；configuration
  `1f1e5dde-a380-4670-9fbb-d70915d74883` rev1/hash
  `sha256:cd357bdd8b0df9f9e65ff9d800f8da5b638e48031fb738ecef9661c32b17269e`，runtimePolicy rev9。
- runtime-apply `9918bfc6-2b42-4472-a4dd-238c98f05684`、verify
  `cb64c207-f7f4-4efb-a707-cd108b06e236`、configure `4850c9ab-2654-444c-a3d0-6f3aa9584c37`、
  enable `34f328e9-c77b-4a88-b830-26530c4a941e` 均 succeeded。
- registration Receipt `5fa0f884-d411-4224-bda3-c5591ebef451`，content hash
  `sha256:2548a517f6f107389c317e0e52cfa41c8991cfb2945c559a15e35d89bce7257a`，登记时 executable=false。
- cutover operation `a7928a35-652a-4eaf-8858-d6d86ba7cabe` 完成 approve/prepare/pause/commit/validate/resume；
  prepare `936b5b02-6152-4ad9-bbd1-9fd0d26189c5`，commit
  `5fe53bde-5e5c-4775-bd93-e11feecfbda2`，validate `18ce0d39-9555-4512-a235-438ea5fffd89`，resume
  `87158672-2299-464d-9655-40dddf00f89a`。最终九路全部指向 BG，claimPaused=false。

## 健康与零副作用边界

- resume 后只读 baseline renewal=10；观察至 renewal22，新增 12 次，last sequence35；三资源保持 pending 且
  observed_release=false，Lease 持续续期。
- BG attempt=0，全租户 running runtime attempt=0、unresolved=0、runtime pending=0、canary=0。
- 十二 saved running Run 与十二 Dataset Receipt 保持；Store Receipt=0、`ecom_link`=0、projection pending=0。
  未启动 Cron/snapshot worker，未手工 `run_definition`，未读商城源数据，230 L0 挂起，未 push。

## 私有证据与回归

- preflight/create `835ab7baff03893f5d12d017579b29aa6a5cf408c887f5660d7115b2ea4c8cf3` /
  `b570a053c2bb7c9ef852f78f45920d22dce3be9da4816287e514b2b8782ca45a`
- prepare/verify `5defbe1ca4b925d1f95d08541ccf7314e57829c79a7de47f070231d8c471e6a7` /
  `bdba42f1fa2516ccff63386606aedace45fb2476ede281643c02a3d09e9a7c4e`
- stage/configure/enable `492df9af55dfd91d94084848370aeef65480e35d546954b078d52c29c7396982` /
  `928c99b34202445bfc09166faec82b6c59fa707cfdb521e0afde61e99ee1bdde` /
  `53ba736dacbf73bcd8b1650318d829747347794bc8912f118cf108b91c9e5930`
- registration `10621e70d787099de0bd2067b8ec6b59674785344563f8b27db1e7d8523675c0`；cutover resume
  `8a6ab570401d5e47277ed966097485fa3c86bb70919a820ad077154148831dc8`；health observation
  `62a504805847ac4bbba9f4692038d3369fe367372d5b0c8183835f07a8b62469`。
- BG/BF 专项回归 `8 passed`；Python 编译与 `git diff --check` 通过。

## 下一波

进入 BG saved-snapshot recovery：plan 先行，纯 HTTP 18181 且 Cron/snapshot worker 关闭；证明唯一 Runtime
Host、第二 Host=0 后再 transfer/recovery/definition enable，最后关闭端口并启动自然 snapshot worker。
