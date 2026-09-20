# BH 直系后继验证

## 结论

`BH_DIRECT_SUCCESSOR_GREEN`。BH installation `7b7d4319-e639-48c9-971b-0efbfb9251ef`、generation
`f6023b7c-ca6f-49ac-b9ff-4dcbca62745c` 已完成创建、runtime-apply、verify、configure、enable、successor
registration 与六阶段 cutover。最终 Binding rev6/epoch3 ready/enabled/unfenced，九路 extension
rev150/group177，definition rev103 disabled。

## 父权威与单 Host

- 唯一父权威为 BG disable operation `95fbec3c-2248-4d43-928c-17b52d3742da` 的 detach Receipt
  `48e4d856-6652-4903-af9f-49bf4774bc0d` / hash
  `sha256:6302314b46ee2699d9a05ef8552df2932fccb385f29a3442eba64c26458ad1b2`；前态九路 legacy
  rev149/group176、Binding rev8/epoch4 detached。
- 全程沿用唯一前台 Runtime Host PID 29815，无第二 Host、无 KeepAlive、无 Cron/snapshot worker；18181 无监听。
- runtime-apply succeeded 后才执行唯一 verify；enable `e0da5710-e778-4db6-85ec-3988d9f00982`
  在 fresh-health 窗口内正式 succeeded，无前置拒绝、无 accepted-unknown、无重发。

## 安装、登记与切换

- BH lock `sha256:c920a20eec94c3f9da2030da31a05f5b8f314f8e9264c5d5d8b4bcc02e4c28fa`；configuration
  `6b63f3e9-6805-48eb-a4cb-08e15d1e52a5` rev1/hash
  `sha256:42681ea6edad421e488076117771df82e7f1b023e68c2adc3d9ebf0a288132f0`，runtimePolicy rev9。
- runtime-apply `7c608516-30ad-4bb4-bef6-9e1b40a3b95f`、verify
  `7a207055-b8c1-4dab-bcca-62c997ef538b`、configure `e4250818-b27d-478a-900e-e10621ca17f5`、
  enable `e0da5710-e778-4db6-85ec-3988d9f00982` 均 succeeded。
- registration Receipt `96fd95f4-0152-4a00-9dca-6645f22326d2`，content hash
  `sha256:22eed45c59b00c074059eac097e11a3ed1fca26985c84ee1b6b4fa510ad5dfac`，登记时 executable=false。
- cutover operation `d21dc573-c75f-47cc-8c9a-e9d2545d5f17` 完成 approve/prepare/pause/commit/validate/resume；
  prepare `86b44113-c556-4f6b-b04c-06a7bf5597d8`，commit
  `7b42093e-56b8-4b35-83ca-2c96229e5118`，validate `7c6e097a-c820-4ecb-b5e1-ebde706ee635`，resume
  `c3369049-3cce-42fb-bed7-15a34134f83e`。最终九路全部指向 BH，claimPaused=false。

## 健康与零副作用边界

- 第一段只读观察以 renewal4 为基线，480秒预算内到 renewal12（新增8次）后如期超时，未写结果、未改变控制面；
  第二段以 renewal12 为新基线，在960秒预算内观察至 renewal24，新增12次，last sequence37。
- 三资源保持 pending 且 observed_release=false，Lease 持续续期；BH attempt=0，全租户 running runtime
  attempt=0、unresolved=0、runtime pending=0、canary=0。
- 十二 saved running Run 与十二 Dataset Receipt 保持；Store Receipt=0、`ecom_link`=0、projection pending=0。
  未启动 Cron/snapshot worker，未手工 `run_definition`，未读商城源数据，230 L0 挂起，未 push。

## 私有证据与回归

- preflight/create `d2766d8d4f5c1d622946bc96ff3215b0822b00ed797549f2f4643f6dbcf85153` /
  `1fdcb6aa99c98118b3c1642f9f9349a654c77e9064c8aa9e227057818e833b26`
- prepare/verify `e9a1e894693ef2b9a823b7bada281b90844f1b2635a8d2418aa22b05c3309f11` /
  `4b6a1a21a0118df682f9b64cbe564b7ecbc5a1295bd5c7b5c7a289562a13087c`
- stage/configure/enable `d6ead803b28ba4bdedbad9d55ece7c7c2813ddaaaaf7c56c2dbb03ac7d480304` /
  `c87f372679f82f3f559907d280555952ea803b3ed245c998966b71d8b156dbd2` /
  `15140dade1f0fbd9232c1e75d1bc7d2a55552c78d612e84ea507a0745f88f884`
- registration `f1c6f6b75e4b45cf180bdae6307fd0dda5d5a57e0e0add0ec401fbbb5106fa7d`；cutover resume
  `cbaf4abbcc145d41dfbdd86f97b6d3512daa76a5e7592ca0e2dbaa691f2b9292`；health observation
  `1a9afc8b390ca40cb0acb0608d35044c5583c4e8b3f5cfdfa8e9502d3880037b`。
- BH/BG 专项回归、Python 编译与 `git diff --check` 必须在提交前通过。

## 下一波

进入 BH saved-snapshot recovery：plan 先行，纯 HTTP 18181 且 Cron/snapshot worker 关闭；证明唯一 Runtime
Host、第二 Host=0 后再 transfer/recovery/definition enable，最后关闭端口并启动自然 snapshot worker。
