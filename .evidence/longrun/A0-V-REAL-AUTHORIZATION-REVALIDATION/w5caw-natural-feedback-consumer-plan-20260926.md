# W5caw｜首段评审反馈自然消费者（施工前方案）

## 上位与当前差距

- 231-5 §3–5 的目标是人工评审提交后由系统从持久命令自然续跑，而非开发者直接调用 `run_one`。反馈 at-least-once 但目标按 Receipt 唯一；旧安装代次、未知 attempt 和已 claim 状态不得自动重发。
- W5cav `a9bbd82d` 已有同事务 `DailyReviewFeedbackWorker.run_one`、`a0v_099` 内部目标及隔离 PG 真链；无租户有界 selector、进程 serve 与启动生命周期。因此仍非自然续跑。

## 本波文件级清单

1. 新增 `services/aos-api/aos_api/ecommerce_growth_feedback_consumer.py`：只读、有界 selector 限定 `org-org/dev-project`、ACCEPT、第一段 `daily_review`、`pending/attempt=0/checkpoint=0`、唯一 Review Origin 与当前 content_review Dispatch/Runtime，旧代/未知/已 claim 一律不返回。`run_once` 对每条调用原 `DailyReviewFeedbackWorker.run_one`（其内部仍锁全组、二次 fence、同事务目标/ack）；单条权限冲突只阻断该条，绝不自动复投已触达/UNKNOWN。
2. 修改 `services/aos-api/aos_api/main.py`：`AOS_ECOM_FEEDBACK_WORKER_ENABLED` 默认关闭，开启只在 ACTIVE Runtime Host、独立 host-only runtime DB 身份与单一主进程通过时启动；共享 Runtime Host stop 事件，Host 终止 fail closed；不启动第二 Host。
3. 新增 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_feedback_consumer.py`：RED→GREEN 验证只读 selector、上界、旧/claimed/unknown 不出队、启动默认关/无 Host 拒绝/Host 停止收束。扩展隔离 PG 测试证明 selector→run_one→目标/ack 一次性；累计回归与当前迁移唯一 head。
4. 本波不自动执行后三段，不新增 Provider/商城源读取、不应用迁移到真实库。没有当前合法安装只阻挡活体验收，不阻挡可独立编码。

## 退出与后续

- 验证须区分代码/隔离 PG 与真实自然周期；8080/18181 的旧状态不能作业务权威。验收时要求第二 Runtime Host=0、Cron/snapshot 仍禁用。
- 验证落盘、m1 提交、D-waves/AOS/Prime 对账后进入 W5cax：真实 `improvement_observation` 的数据来源门与 EffectReview Owner，不把静态“待观察”文本提升为效果。
