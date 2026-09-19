# BD 单终态正式退休验证

## Authority 与执行

- preflight 精确读回 BD installation `c2d6ef97-30ec-4980-9421-54a899607853` / generation
  `f5e01f1d-e6c5-425a-9145-6f7a82ec65e5`，Binding rev6/epoch3 enabled/ready/unfenced，三资源 live，
  九路 extension rev138/group165，definition rev94 disabled。
- attempt 历史严格为唯一 revision 61 `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED /
  IngressJournalConflict`；十二 Run running、十二 Dataset Receipt，Store/link/projection/canary 全零。
- 唯一 disable operation `f5f52787-c6f1-468b-9e7e-878113942c65` 由唯一 Runtime Host 自然领取；
  `claimedByHost=true / resendDisable=false`，未换 key、未重发。

## 正式终态

- audit 为 `BD_TERMINAL_RETIREMENT_GREEN`：Binding rev8/epoch4 disabled/fenced/unknown，三资源全部 released；
  九路恢复 legacy rev140/group167。
- operation revision 6 succeeded；生命周期 Receipt 恰为 `fence → detach`：detach Receipt
  `c896fec3-dbe2-46fe-be60-3cc249b4b4ed` / hash
  `sha256:8845a269e68dd54bfa89ca1e8a1f5785e199fb80985f86d08f93b5b570581495`。
- definition 继续 rev94 disabled；running/unresolved/runtime pending、Store Receipt、`ecom_link`、projection pending、
  canary 全零，audit `externalEffects=0`。

## 证据与验证

- preflight/request/process/audit 私有结果 SHA-256 依次为
  `16bb69581d5a7f076924c5d3fad2358a22a7686fb8497ce91fd4e9d6a0e4ab1a`、
  `455f50854eca82cd4021833dac3a193ab3e55a28a05a55020cb413aab9282bdd`、
  `fe072e15e8a09a7ddbadedca7ebb9af645702d4675977f2f2f1cac0652c03f6f`、
  `f28fd5ddf619d04ebe42ef0e6a5c4415c9246cb7de8395b8344e1ae2f3140325`。
- BD/BC/BB terminal retirement 组合回归 `6 passed`；Python 编译与 `git diff --check` 通过。
- 本波未启动 worker、未创建第二 attempt、未读取商城源数据、未 push、未改其他分支；230 L0 继续挂起。

## 下一波

只能从 exact detach Receipt `c896fec3-dbe2-46fe-be60-3cc249b4b4ed` 方案先行创建 BE direct successor；禁止
恢复 BD 或复用其已终态 attempt。
