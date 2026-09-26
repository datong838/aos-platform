# W5CB4 P2g19：当前首链启用前只读权威清点

日期：2026-09-27。方案 `m1@7cd9ed87`。本波只读，无当前业务效果写入。

## 已核事实

- 本仓库 `m1@7cd9ed87`、docs `m1@e0eb627e`；仓库仅有两份用户原有未跟踪的 `w5c8i-test-only-*` 文件，未触碰。8080、18181、5173 均无监听。第十八增量浏览器在安装目录门前显示离线，临时 Vite 已停。
- 当前 `.env` 没有有效 `AOS_DATABASE_URL` 或新反馈 worker flag；带注释的示例不算启用。`aos_api.db` 因此使用代码中的开发默认 DSN；只读连接返回 `current_user=aos_runtime, current_database=aos_meta`，该库 `public` 用户表数为 0，`to_regclass` 对 `bundle_installation`、`extension_runtime_host_identity`、`ecommerce_growth_feedback_command` 均为 null。此连接**不是可证明的当前生产权威库**，不得据此宣称真实安装不存在或 Host 停止。
- 代码迁移目录为单 head `a0v_106`，不等于当前目标库已迁移。新第二/正式评估/第三段 worker 在代码中默认 false；无运行服务和当前签名安装/权限/来源/预算/真人审批/Runtime Host 的独立读回，本波判定真实启用条件 **NOT_VERIFIED**。不尝试启动服务、改环境、强启 worker 或触发旧 Run。

## 明确的下一编码缺口

- `ImprovementFeedbackWorker.run_one` 在同一事务内 `target.read_receipt`、反馈 checkpoint 读回后 `conn.commit()` 即返回 `IMPROVEMENT_PENDING_ACKED`。该成功返回缺提交后独立连接的目标 Receipt/checkpoint/原命令读回；提交结果未知时当前消费者会将异常作为不可预期任务失败，但不得据此自动重发。原同库测试中的事后 SQL 与下一段 EffectReview 读回不能替代 worker 自身提交后确认合同。
- 下一波 P2g20 先方案、RED，再只在第二段 worker 增提交后独立只读核对；未知/漂移抛稳定 `Unknown` 并让自然 serve 失败关闭，不创建第二 attempt。专项、原同库与累计回归后 verification、m1 提交和 AOS/Prime 更新。当前实例继续 off。

## 判定

- 代码/隔离 PG：`VERIFIED` 到各波证据边界。
- 当前签名安装、Host、自然 worker、真实来源/审批/预算与浏览器三段：`NOT_VERIFIED`（当前 API 离线且配置数据库是空的开发默认库）。
- 真实首链自然完成、效果改善、Wiki 已入库：`NOT_VERIFIED`，不可发布。旧十二 Run、商城源、230 L0 均不动。
