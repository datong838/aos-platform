# BC 单终态正式退休验证

## Authority 与执行

- preflight 精确读回 BC installation `3b895c30-34ca-4710-b978-02645d49c83a` / generation
  `31776dcd-e28f-4b6d-ae45-75fb0ab5a505`，Binding rev6/epoch3 enabled/ready/unfenced，三资源 live，
  九路 extension rev135/group162，definition rev91 disabled。
- attempt 历史严格为唯一 revision 61 `abandoned / ATTEMPT_LEASE_EXPIRED`；无 running/unexpected attempt。
  十二 Run running、十二 Dataset Receipt，Store/link/projection/canary 全零。上一波 worker 在数据库
  elapsed=1800 秒精确停止，终态 elapsed=1893 秒只包含 lease-expiry 等待；本波不恢复 worker。
- 唯一 disable operation `b713c722-902f-4486-b3bb-4eca02a621b7` 由唯一 Runtime Host 自然领取；
  `claimedByHost=true / resendDisable=false`，未换 key、未重发。

## 正式终态

- audit 为 `BC_TERMINAL_RETIREMENT_GREEN`：Binding rev8/epoch4 disabled/fenced/unknown，三资源全部
  released；九路恢复 legacy rev137/group164。
- disable operation revision 6 succeeded；生命周期 Receipt 恰为 `fence → detach` 两张，definition 继续 rev91
  disabled；唯一 terminal attempt 与十二保存 Run/Receipt 不变。
- running/unresolved/runtime pending=0，Store Receipt=0、`ecom_link`=0、projection pending=0、canary=0；
  audit `externalEffects=0`。

## 证据与验证

- preflight/request/process/audit 私有结果 SHA-256 依次为
  `2db1ad8814a3544235312f621f3b6b65d39f9cdf348acc6e24b4439023358f50`、
  `30e69813412850763d4148920b57ed42064a2a63c4a72be64dad88b2df1af7c5`、
  `cb6a970802bbaf6b89071d2aabb09c229af05a8504abca2505bfc7bb6da3decd`、
  `e3a9b082013902cedb7909d7d6dd62ec5b44a3022d52b3f5fcaea96168b74982`。
- BC/BB/BA/AZ/AQ terminal retirement 组合回归 `9 passed`；Python 编译与 `git diff --check` 通过。
- 本波未启动 snapshot worker、未创建第二 attempt、未读取商城源数据、未 push、未改其他分支；230 L0
  继续挂起。

## 下一波

只能从 operation `b713c722-902f-4486-b3bb-4eca02a621b7` 的 exact detach Receipt 方案先行创建 BD direct
successor；禁止恢复 BC 或复用其已终态 attempt。
