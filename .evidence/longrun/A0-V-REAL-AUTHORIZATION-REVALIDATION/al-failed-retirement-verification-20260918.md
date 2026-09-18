# AL failed retirement 验证（2026-09-18）

## Rules

- 仅由原 Runtime Disable Owner 处理 AL；先冻结 intent，再提交一次 disable 请求。
- 只消费该 operation 的既有 outbox delivery；宿主已处理时只读对账，禁止重发。
- definition、十二 Run 与保存输入不得改写；Store 零提交边界必须在每个阶段保持。
- dev-org 仅作零越权 canary；不以退休成功声明真实经营闭环完成。

## 第 1/6 步：精确前置

AL 为 etag5 active，binding rev6/epoch3 enabled+unfenced+ready，三资源 pending，九路 extension rev87/group114；definition rev51 disabled。failed attempt revision382 唯一，十二成员 Run 仍 running，Store Receipt/link/pending projection 均为零；全租户 running attempt、AL unresolved occurrence、pending runtime operation、dev-org canary 均为零。

## 第 2/6 步：正式请求

以 bindingRevision6 和 etag5 提交唯一 disable，idempotency key 为 `a0v-qyh-failed-al-retirement-20260918-v1-disable`。operation `c9328938-3b56-4a8d-ac38-54f7abf70416` 返回 accepted，未创建第二笔请求。

## 第 3/6 步：宿主处理与对账

宿主在本地显式 process 前已经消费该 delivery。脚本检测终态后走 reconcile 分支，记录 `claimedByHost=true`、`resendDisable=false`，没有再次 claim 或重新提交 disable。

## 第 4/6 步：终态

- binding rev8/epoch4 disabled+fenced+unknown；
- 三资源全部 released；
- 九路恢复 legacy，revision89、groupRevision116；
- operation succeeded，lifecycle 仅有 `fence/detach` 两阶段；
- detach Receipt `bd92aa48-77b6-4c34-82f9-0ede171083b3`，hash `sha256:b8990ed467aed1bdfc40e5fb56e4455e2ece7114045f37a15f8f4099a313e1df`；
- definition 仍为 rev51 disabled，十二 Run 与失败边界保持，Store 三项仍为零，canary 为零。

## 第 5/6 步：专项验证

`test_a0v_al_failed_retirement.py` 通过；脚本编译与 diff whitespace 检查通过。首次 process 校验曾按方案中的预测 epoch5 拒绝继续；只读对账确认权威终态为 epoch4 后同步修正方案、脚本和测试，再次执行只做终态 reconcile，没有产生额外副作用。

## 第 6/6 步：下一波

下一波以本次唯一 detach Receipt 为 direct predecessor 新建 AM。文件级范围为 AM replacement lifecycle、专项测试及验证证据；依次完成 approved → prepare → verify → stage → configure → enable，随后用 successor registration 把九路从 legacy 原子切到 AM。AM 未注册前不迁移 definition 或执行保存输入。
