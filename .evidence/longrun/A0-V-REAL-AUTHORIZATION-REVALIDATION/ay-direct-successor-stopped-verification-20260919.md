# AY 直系后继停止边界验证

## 已完成步骤

- preflight 精确验证 AX detach operation `8589a12c-aec2-4035-8937-f358dd1a8488`、detach Receipt
  `622c8e25-ec0f-40dd-bf1f-ea57d180a800` / hash
  `sha256:583954da94992d30f7c5f9133c235eb3b17e0d8d190c27d61fe47621d41a6870`、legacy
  rev125/group152 与 definition rev79 disabled。
- Owner 创建全新 AY installation `81df994f-23ce-4448-ac46-366aaee63924`，lock hash
  `sha256:7826b7400df634c9ad5f538b7db24026fc8930ee4bf6627b5d13277b2fa6afc5`；未复用 AX identity。
- stage 生成 generation `a1069f60-46f5-41a8-bd18-61ed677eb3bd` 与 configuration
  `ce24590a-479e-4a5e-94ab-01d138e0675c` rev1/hash
  `sha256:579a652e471f626f08e25f80f19b4e9f77b91531a456dac87ef2f2220e1cff89`，明确引用 current
  runtimePolicy rev9。
- runtime-apply `fbd3b27a-d802-4ac3-8fd5-0549510e8455`、runtime-verify
  `93b451b8-6e17-4014-b61c-508aeb5880ec`、configure `ce9d83c9-103d-481d-b048-09478b39934c`
  均正式 succeeded。

## 停止原因与冻结边界

- enable operation `24a85b28-f00d-43cf-ba5d-28f064c74f6a` 已 accepted，但唯一 Runtime Host 仅领取
  outbox event `8c11ac0e-9709-496d-92c9-73c21528f0fa` 一次；operation 在
  `2026-09-19T13:19:50.776425+00:00` deadline 后仍为 revision1 accepted/accepted，outbox attempt=1、
  deliveredAt=null。
- 两次 successor preview 均在写入 registration intent 前 fail-closed 于 tenant 未 drained；未执行 register，未开始
  cutover，预留 operation `98a056c1-bba0-4073-bda1-0fa16d214f10` 从未提交。
- 为阻止晚到未知提交，精确识别并优雅停止唯一 Runtime Host PID 27382；状态文件读回
  `RUNTIME_HOST_STOPPED`。未启动第二 Host、未重发 enable、未换 idempotency key。
- 冻结时 AY Binding rev3/epoch2 disabled/fenced/desired disabled/observed unknown，三资源 released；九路仍为
  legacy rev125/group152，definition rev79 disabled，AY attempt=0。
- 12 Runs 仍 running、12 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending 与
  `dev-org/dev-project` canary 均为 0。

## 证据与验证

- preflight/create/prepare/verify/stage/configure/enable 私有结果 SHA-256 依次为
  `1c5c98b276569ad83695c6c550d3348ecd629e2f29c0b7b568290ce60901662c`、
  `be6130d5b72528eb3f083c704715808e996d532bf57d1fbca34f60093cdebd5a`、
  `c933734f8280fa5d95b6536c4beab14bc0af4a262cd758d85303f687e0fa231d`、
  `c04d8604304dc2794e310fd7fef9ea29367ba55c0177de2d745c4eec37e0c10c`、
  `634ddf19a7703edd7af4e1cca437ada2f548001c7bd86f750f16e9062f90a5e2`、
  `b144fae637cb421b895766e38fb677c43ab584e9f6e602301b9b7de695aef6f5`、
  `2dd973ed8ab6334872b5b7f90a348a9293f78243225f7708ee22c4777a083249`。
- AY/AX replacement、successor、cutover、health observer 专项回归 `6 passed`；Python 编译与
  `git diff --check` 通过。
- 本波未读取商城源数据、未 push、未改其他分支；230 L0 继续挂起。

## 下一波

以 AY enable accepted-unknown、Binding rev3/epoch2 disabled/fenced、三资源 released、Host stopped 与零业务
副作用为冻结边界，方案先行走正式取消/settlement 与 retirement；禁止恢复本次 enable、禁止 register/cutover。
只有 exact cancellation/detach Receipt 落盘后，才允许创建 AZ direct successor。
