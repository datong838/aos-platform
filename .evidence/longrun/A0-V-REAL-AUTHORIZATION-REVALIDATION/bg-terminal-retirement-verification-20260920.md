# BG 单终态正式退休验证

## 结论

`BG_TERMINAL_RETIREMENT_GREEN`。BG installation `c52ab6db-176e-4378-ac88-2ee1bfc58487` / generation
`477c3f92-06f0-4dae-9445-ce6d09c3f462` 已由唯一 disable operation
`95fbec3c-2248-4d43-928c-17b52d3742da` 正式退休。

## 前置权威

- definition rev103 disabled；snapshot worker 与 18181 均停止，唯一外部 Runtime Host PID 29815 运行。
- 固定唯一 attempt `a42bc506-7e3c-48cd-bde7-1eb0b1adc93f` 为 revision61
  `abandoned / ATTEMPT_LEASE_EXPIRED / null`；unexpected attempt=0。
- 十二 Run running、十二 Dataset Receipt；Store Receipt、`ecom_link`、projection pending、canary 全零。
- 退休前 Binding rev6/epoch3 enabled/ready/unfenced，三资源 live，九路 extension rev147/group174。

## 执行与终态

- preflight 为 `BG_TERMINAL_RETIREMENT_PREFLIGHT_GREEN`，externalEffects=0；request-disable 唯一 accepted，未重放。
- 首次 process 的 detached 探测发生在 Host 完成前，紧随其后的 accepted 探测发生在 Host 完成后，因此 exact
  snapshot fail closed。未重发、未另行领取；只读确认 operation 已 succeeded 后重入同一步，读回
  `claimedByHost=true`、`resendDisable=false`。
- fence Receipt `190d09a2-38a0-4d48-88f5-06fad4841a73` / hash
  `sha256:ee4aa9324b3400933e5ede14e0c650e3ab996f574a358e89d0c507d43fd52d9c`；detach Receipt
  `48e4d856-6652-4903-af9f-49bf4774bc0d` / hash
  `sha256:6302314b46ee2699d9a05ef8552df2932fccb385f29a3442eba64c26458ad1b2`。
- 最终 Binding rev8/epoch4 disabled/fenced/unknown，三资源 released；九路 legacy rev149/group176；definition
  rev103 disabled。operation rev6 succeeded，lifecycle 恰为 fence→detach 两张 Receipt。

## 验证与边界

- 私有结果 SHA-256：preflight
  `beb5b26435a807d2bd004f2c9a9cabff65fbce248ae11720ac4d0eab07c52492`、request
  `d5951fc9add1cc8dd4844ae527d23209604a83bc850e41f57b3bc6348c344cd6`、process
  `e3766af7b9c15ce0894e0b5a0f903b8cfb9c69e14ef05c989c03f7dc02251ec0`、audit
  `9c0281ec991302cde12763fbb4b80c1528a50423daa967b49edaeb26de6d51f0`。
- BG/BF/base retirement 专项回归 `5 passed`；Python 编译与 `git diff --check` 通过。
- 本波未启动 worker、未创建第二 attempt、未读取商城源数据、未 push、未改其他分支；230 L0 继续挂起。

## 下一波

以 exact detach Receipt `48e4d856-6652-4903-af9f-49bf4774bc0d` 为唯一父权威，方案先行创建 BH direct
successor；禁止复活 BG 或创建 BG 第二 attempt。
