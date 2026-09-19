# BA 单终态正式退休验证

## Authority 与执行

- preflight 精确读回 BA installation `9110f69b-bb31-4d17-98e8-6c5ed1d9234f` / generation
  `197f5036-656a-4b58-a261-e93e2fffea18`，Binding rev6/epoch3 enabled/ready/unfenced，三资源 live，
  九路 extension rev129/group156，definition rev85 disabled。
- attempt 历史严格为唯一 revision 61 `abandoned / ATTEMPT_LEASE_EXPIRED`；无 running/unexpected attempt。
  十二 Run running、十二 Dataset Receipt，Store/link/projection/canary 全零。上一波已披露的 elapsed=1909 秒预算
  偏差不被改写，也不影响本波 exact terminal 身份。
- 唯一 disable operation `4668c723-0acc-446a-9c0d-80118e2f380c` 在明确未被 Runtime Host 领取后，由原
  RuntimeDisableConsumer 领取一次；`claimedByHost=false / resendDisable=false`，未换 key、未重发。

## 正式终态

- audit 为 `BA_TERMINAL_RETIREMENT_GREEN`：Binding rev8/epoch4 disabled/fenced/unknown，三资源全部
  released；九路恢复 legacy rev131/group158。
- disable operation revision 6 succeeded；生命周期 Receipt 恰为 `fence → detach` 两张，definition 继续 rev85
  disabled；唯一 terminal attempt 与十二保存 Run/Receipt 不变。
- running/unresolved/runtime pending=0，Store Receipt=0、`ecom_link`=0、projection pending=0、canary=0；
  audit `externalEffects=0`。

## 证据与验证

- preflight/request/process/audit 私有结果 SHA-256 依次为
  `e73e7fc54d790d2808129b921de005ce894f3c024ee1e79c2ba1e2ca8bdfee42`、
  `54d1a1d9c2cd9477a395450fbdbfaf09d185e718bdcfa4ba216cbd97b65b800c`、
  `bfa38051c37e6c28879aeb7c112569006a52960322bb7fe860f134a1c67fb31e`、
  `685d0b5a32b7f66c42e46b43ac808bf4bf7381080eb50c280db9dc2862d84617`。
- BA/AZ/AQ terminal retirement 组合回归 `5 passed`；Python 编译与 `git diff --check` 通过。
- 本波未启动 snapshot worker、未创建第二 attempt、未读取商城源数据、未 push、未改其他分支；230 L0
  继续挂起。

## 下一波

只能从 operation `4668c723-0acc-446a-9c0d-80118e2f380c` 的 exact detach Receipt 方案先行创建 BB direct
successor；禁止恢复 BA 或复用其已终态 attempt。
