# AM 失败恢复正式退休验证

## 1. 前置门禁

- definition rev54 disabled；AM 两笔 recoverable Store attempt 精确为 failed revision627/86，同 generation
  无其他 attempt，running=0。
- installation `fd28d180-db24-4568-a848-101fcd3aa3c5` etag5 active；binding rev6/epoch3
  enabled/ready/unfenced；三资源 pending；九路 extension rev90/group117。
- 12 Run running、Store Receipt/ecom_link/projection pending=0；unresolved/runtime pending/dev-org canary=0。
- `scripts/a0v_am_failed_retirement.py preflight` 返回
  `AM_FAILED_RETIREMENT_PREFLIGHT_GREEN`，externalEffects=0。

## 2. 正式执行

- request-disable 使用 `a0v-qyh-failed-am-retirement-20260919-v1-disable`，创建 operation
  `6d94d641-6fc3-4edd-801c-69114d633c0c`；accepted revision1，expected binding revision6，非 replay。
- 常驻 Host 已领取原 disable outbox；`process-disable` 只读识别终态并冻结
  `claimedByHost=true, resendDisable=false`，没有第二次发送。
- lifecycle receipts 精确为 `fence → detach`，operation succeeded revision6。

## 3. 终态

- binding rev8/epoch4 disabled/unknown/fenced；三资源全部 released。
- 九路 legacy route rev92/group119；definition 保持 rev54 disabled。
- running/unresolved/runtime pending/dev-org canary=0。
- 两笔 failed attempt、12 Run 与 Store 零提交边界保持不变。
- `audit` 返回 `AM_FAILED_RETIREMENT_GREEN`，externalEffects=0。
- AM/AL 退休与 saved recovery 相邻回归 4 passed；静态编译和差异检查通过。
- 浏览器只读复验 AOS v1.6.5 仍为“暂无可见工作台入口”，门禁 NOT GREEN。

## 4. 下一波

AN 只能把本次 operation 的 detach Receipt 作为 direct predecessor；使用全新 installation/generation、配置与
execution epoch。parent feature 完整提交、专项回归和安全空窗 Host/Worker 重载完成前，AN saved definition 必须保持
disabled，不得手工 `run_definition`。
