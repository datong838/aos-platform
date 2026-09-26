# W5CB4 P2g25：RETURN 自然拾取默认关闭门验证

日期：2026-09-27。方案先行 `m1@527cb64b`。此波只给 P2g24 的已持久内部返工目标增加选择、轮询和独立启动门；没有迁移、当前库写入、自然 worker 启用、Provider/商城源/旧 Run 操作。

## RED 与新鲜验证

- RED：新增 `CurrentContentReturnConsumer` 专项先因该类不存在在测试收集期失败，再实现 bounded selector/run_once/serve。启动门测试从原三项扩为四个独立 flag，默认 `false`，不复用 ACCEPT 的启用权。
- 一次性完整 `a0v_106` 同库的正式 RETURN 原对象链中：选择器只在原 feedback checkpoint=0、单段 pending/attempt=0、当前 Host dispatch/runtime ready、原 Run running/Task executing、正式 ReturnDecision 所指最新 queued `content_generate` StepRun 时返回唯一 command。无九操作锁不能消费；当前 dispatch fence=true 时选择为空，ack 后选择为空。实际 ack 仍由 P2g24 owner 在持锁事务内重验。
- `dev-org/dev-project` 仍仅为零 canary；无跨租户目标。单元覆盖 limit 1–32、选择器身份、Host 不 ACTIVE、非法 flag/缺独立 runtime DSN、stop 后状态与提交未知导致 task `FAILED_CLOSED`。未知异常不被吞成普通可跳过候选；无第二次 claim。
- 新鲜累计：RETURN/startup 专项 `35 passed`；反馈端口、当前评审终态与同库链 `69 passed, 3 skipped`（最后新增一条 latest-attempt 负向后又重跑专项）。`compileall`、`git diff --check` 通过；单迁移头 `a0v_106`。一次误在错误工作目录运行的测试命令未启动 pytest，也未修改代码/库；随后在正确目录重跑专项通过。

## 一致性与边界

- `AOS_ECOM_CONTENT_RETURN_WORKER_ENABLED` 缺省关闭；只有 Runtime Host task ACTIVE、未结束和独立 runtime DSN 可读才创建自然任务，每轮复核 Host，stop 正常退出。当前 8080/18181 仍未监听，真实恢复库 `STOP_MIGRATION` 不变。
- 自然 worker 只把已由真人正式 RETURN 写入的 queued 返工目标确认接收，**不启动第 2 次内容生成**，不重用旧审批或预算。隔离测试不是真实用户审批/签名安装/自然经营结果。纯后端 worker 门，浏览器本波不适用。
- 下一波：定义/实现被退回的 queued `content_generate` 如何在新的内容版本、当前安装、重新批准与独立预算 hold 后安全执行；若条件不足则保留待办与可操作阻断，不手工代跑。
