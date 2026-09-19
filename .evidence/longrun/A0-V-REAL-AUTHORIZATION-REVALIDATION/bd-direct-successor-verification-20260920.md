# BD 直系后继验证

## 结论

`BD_DIRECT_SUCCESSOR_GREEN`。BD installation `c2d6ef97-30ec-4980-9421-54a899607853`、generation
`f5e01f1d-e6c5-425a-9145-6f7a82ec65e5` 已完成创建、runtime-apply、verify、configure、enable、successor
registration 与六阶段 cutover。最终 Binding rev6/epoch3 ready/enabled/unfenced，九路 extension
rev138/group165，definition rev91 disabled。

## 父权威与单 Host

- 唯一父权威为 BC disable operation `b713c722-902f-4486-b3bb-4eca02a621b7` 的 detach Receipt
  `39bb3f98-78b6-444b-9d5c-a51991b03f42` / hash
  `sha256:7351a8aca2751c721b96ef1c72352318a507a18598930e13fbc79667f3bc169c`；前态九路 legacy
  rev137/group164、Binding rev8/epoch4 detached。
- 全程沿用唯一前台 Runtime Host PID 29815，无第二 Host、无 KeepAlive、无 Cron/snapshot worker；18181 无监听。
- runtime-verify succeeded 后连续 stage/configure/enable；enable `81a7f55e-26f5-4376-9a87-76452eaa3232`
  在 fresh-health 窗口内正式 succeeded，无 accepted-unknown。

## 安装、登记与切换

- BD lock `sha256:0acab1c9950e014737c8e5814750bca0118bf265e9dfeb382a52d32b45a71547`；configuration
  `2c19490b-b82f-48d4-b035-00c2824a6d7a` rev1/hash
  `sha256:678f6104653a499b05610e5272a96200bf35fbefba8a5804c5896e597ea531b3`，runtimePolicy rev9。
- runtime-apply `64e80251-affc-4155-82ae-faafc9cdcaa1`、verify
  `27b1ac18-31e1-4cec-8a9a-71161c1cfd2f`、configure `cb904100-12b7-418a-a53f-3624f7717476`、
  enable `81a7f55e-26f5-4376-9a87-76452eaa3232` 均 succeeded。
- registration Receipt `ac40bc44-b1ff-4da3-979a-e69f76030671`，content hash
  `sha256:d52835f4e81e930d9448d360ccc21216b4d145fe1e94e472aaf63b09ca3ae8b0`，登记时 executable=false。
- cutover operation `e4baf529-cc27-4a0d-aa18-139b22f6dd19` 完成 approve/prepare/pause/commit/validate/resume；
  prepare `8745a623-76e7-435f-9148-823ea5b19e58`，commit
  `1de749bc-3568-49c1-86db-8b4fde646b2a`，validate `0d175c09-f493-422a-ab93-27b3ade41363`，resume
  `ad89c72b-e518-46e5-adf0-b03f62e639ce`。最终九路全部指向 BD，claimPaused=false。

## 健康与零副作用边界

- resume 时刻回溯 baseline renewal=4；只读观察至 renewal16，新增 12 次，last sequence29；三资源保持
  pending 且 observed_release=false，Lease 持续续期。
- BD attempt=0，全租户 running runtime attempt=0、unresolved=0、runtime pending=0、canary=0。
- 十二 saved running Run 与十二 Dataset Receipt 保持；Store Receipt=0、`ecom_link`=0、projection pending=0。
  未启动 Cron/snapshot worker，未手工 `run_definition`，未读商城源数据，230 L0 挂起，未 push。

## Fail-closed 过程记录

- runtime-apply 刚 accepted 后立即调用 verify，被“applied install without committed binding required”前置校验拒绝；
  未创建 verify intent/operation。只读确认 apply rev13 succeeded 后才执行唯一正式 verify，未重发 apply。

## 私有证据与回归

- preflight/create `b58fbe2a0972edee22a486d10fd50b3a79f483eca9f39da898e8469c26d0bc86` /
  `b985b349e62bd9956129819358904d522a44e2d20a48006aebb8adf6e95caad4`
- prepare/verify `5840ecf1000a01aa9c573f670d8bd7bb520d35e96cb28bb68621b06d2a907683` /
  `bc9205684aecbd5b7e75e1dbaca62b864ec3bdec6ffc00ac17c685e48b45920b`
- stage/configure/enable `96a3e24b4f2033fe3d06181e154dc08b54d5b973a847f03a4e805dc29f5cd5b4` /
  `b5446c30770cb9c0acdb395d2644f23a315c6f745dc6497db45fbe4c0140bf0d` /
  `b2c1c89c1328063e8bc303dd0527464d179dd64e667790213b65640b711de5ab`
- registration `096417258fc3a84dd0e9fa0275227f5428212218745ace48701b57f33659959c`；cutover resume
  `0543b354285bf9370251a41c847ec6bb60ef825409544dcf2c36e893d1fa89ba`；health observation
  `f9949a47601062a0fbe2409f93f81bed461ad092199468bc978a954eaa1e1dbc`。
- BD/BC 专项回归 `8 passed`；Python 编译与 `git diff --check` 通过。

## 下一波

进入 BD saved-snapshot recovery：plan 先行，纯 HTTP 18181 且 Cron/snapshot worker 关闭；证明唯一 Runtime
Host、第二 Host=0 后再 transfer/recovery/definition enable，最后关闭端口并启动自然 snapshot worker。
