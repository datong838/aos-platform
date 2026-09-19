# AZ 两终态正式退休验证

## Authority 与执行

- preflight 精确读回 AZ installation `40eee6d9-fb03-4657-a83e-aeb38ec4aeeb` / generation
  `7b6befaa-2f92-4e62-85f9-0ca060ec4b90`，Binding rev6/epoch3 enabled/ready/unfenced，三资源 live，
  九路 extension rev126/group153，definition rev82 disabled。
- attempt 历史严格为 revision 61 failed deadline/conflict 与 revision 4 abandoned lease-expired；无 running/
  unexpected attempt。十二 Run running、十二 Dataset Receipt，Store/link/projection/canary 全零。
- 唯一 disable operation `06849afe-ee19-486d-9d56-5247e947d8ab` 由现有 Runtime Host 自然领取；
  `claimedByHost=true / resendDisable=false`，未换 key、未手工重发。

## 正式终态

- audit 为 `AZ_TERMINAL_RETIREMENT_GREEN`：Binding rev8/epoch4 disabled/fenced/unknown，三资源全部
  released；九路恢复 legacy rev128/group155。
- disable operation revision 6 succeeded；生命周期 Receipt 恰为 `fence → detach` 两张，定义继续 rev82
  disabled；两次 terminal attempt 与十二保存 Run/Receipt 不变。
- running/unknown/runtime pending=0，Store Receipt=0、`ecom_link`=0、projection pending=0、canary=0。

## 证据与验证

- preflight/request/process/audit 私有结果 SHA-256 依次为
  `b2e87656a7ff13a1ce944f5c153049a5bea18b52501c75634fa845c3b9c23015`、
  `08f6ea7cd7a979e616afb34933d153371d8457051930f5fe53faccd652b798e3`、
  `c0dc29ef16129a3f3fd287ec161c65d241cd9744dbe8469db152a6d2938970ca`、
  `6b103d1ef920268c6622ec84131fb3a3587871d70e113a6ec5a67a929d0c252a`。
- AZ/AX/AQ retirement 组合回归 `5 passed`；Python 编译与 `git diff --check` 通过。
- 本波未启动 snapshot worker、未创建第三 attempt、未读取商城源数据、未 push、未改其他分支；230 L0
  继续挂起。

## 下一波

只能从 operation `06849afe-ee19-486d-9d56-5247e947d8ab` 的 exact detach Receipt 方案先行创建 BA direct
successor；禁止恢复 AZ 或复用其已终态 attempt。
