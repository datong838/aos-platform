# W5CB4 P2g｜自然 Review 终态拾取默认关闭（2026-09-27）

## 结论

- `ContentReviewStepOwner.run_once/serve` 以有界当前 ACCEPT Receipt 选择器自然调用原 `run_one`；已知当前权威冲突只返回 `BLOCKED_CURRENT_AUTHORITY`，未知提交/读回与意外数据库错误抛出使 worker 停止，不自动重领。`serve` 只运行于正租户 `org-org/dev-project`，每轮检查 Runtime Host 仍存活。
- `main.py` 新增独立 `AOS_ECOM_CONTENT_REVIEW_STEP_WORKER_ENABLED`，默认 false。显式启用须 active Runtime Host 与独立 runtime DSN；无效开关、无 Host/DSN、启动即失败均 FAILED_CLOSED，立即失败不遗留后台任务。启动顺序在内容生成终态之后、反馈消费者之前；本波**没有启用当前实例开关**。
- 正式 `a0v_105` 一次性库在同一原受控对象链由非超级 serializable `aos_runtime` 的 `run_once` 自然选出唯一 Receipt，经过九操作锁/Host 复验完成原 Run；之后反馈选择器才出现唯一 command。重复原 Receipt 无第二 attempt。签名模板 resolver、模拟 reviewer、受控来源/Provider、测试身份均不能代替当前真实安装和人类决定。

## 验证与边界

- RED：缺 `_start_content_review_step_worker` 导致测试导入失败；启动即失败时后台 task 残留。两项均已用最小代码修复。专项新 Owner/同库 `22 passed`；原生成/反馈启动回归 `12 passed`；累计内容相关 `318 passed, 35 skipped, 7 warnings`。`git diff --check` 通过。纯后端运行门无浏览器验收对象。
- 自然 review 终态拾取已有代码但生产默认关闭。未证明当前实例签名 Bundle/真实 reviewer/内容事实、Host Receipt 自然生产、反馈第一段真正 `run_once` 消费、EffectReview/总控/Wiki 候选；不把当前进度宣布为业务闭环。

## 下一波

- 在一次性全迁移库沿本波唯一 feedback command 跑正式 `CurrentFeedbackConsumer.run_once`，独立读回 `daily_review` target Receipt 与 checkpoint；再核 improvement/memory segment 到 EffectReview/总控/Wiki 候选的真实接收端与治理边界。当前实例缺签名模板/人类决定则 no-effect，旧 12 Run 退休与失败快照逐行补齐仍后置，商城源不读，230 L0 不动。
