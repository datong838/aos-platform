# W5CB4 P2g20：第二段反馈提交后独立读回

日期：2026-09-27。方案先行提交 `m1@861e9393`；当前实例消费者仍默认关闭。本波不读商城源、不触旧十二 Run。

## 代码与边界

- `services/aos-api/aos_api/ecommerce_growth_improvement_target.py` 的第二段 worker 保留原同事务 claim→target put/read→ack/checkpoint 校验，在 `commit()` 后改用**新的租户 scoped read-only 连接**核原 ACCEPT 命令/四个 exact 来源、第一段已 ack 与原 Receipt、第二段 target Receipt/body、attempt=1/acked/checkpoint=2/targetId。提交异常、独立读失败或漂移均抛 `ImprovementFeedbackUnknown`，不得回报 `IMPROVEMENT_PENDING_ACKED` 或自动重投。
- 自然选择器仅吞明确的前置 `Conflict`/Host 拒绝，不吞 `Unknown`；其 `serve` 因异常退出，由已有 app 任务门标记 FAILED_CLOSED。没有新增迁移/表、放宽权限或改其他反馈阶段。

## 验证

- 故障注入覆盖 commit 结果未知、独立连接失败、独立读回 attempt 漂移以及自然选择器不吞 Unknown；专项 `test_ecommerce_growth_improvement_target.py` **14 passed**。
- 原一次性全迁移同库链以原同一 ACCEPT 命令、非超级运行身份，在提交后经过显式第二独立连接读回；同库文件 **7 passed**。生产默认连接为 `connect_read_only`；隔离 clone 因现有 `runtime_connect` 接缝使用新的运行身份连接，未冒称当前生产实例。
- 相关累计 `uv run pytest tests/extension_runtime/test_ecommerce* tests/aip/test_aip_memory_store.py tests/test_ecommerce_workshop_api.py tests/test_ecommerce_workshop_task_cockpit.py -q`：**1028 passed，191 skipped**；compile、`git diff --check`、Alembic 单头 `a0v_106` 通过。纯后端，浏览器不适用。
- 流程偏差：本切片先落最小实现再补故障注入测试，没有保存新增测试相对旧实现的独立 RED 运行记录；不以此声称严格 RED→GREEN。上述专项、同库与累计 GREEN 是实际可复核结果，后续波恢复先 RED 的顺序。

## 未完成与下一波

- 当前 8080/API 离线，`.env` 使用空的开发默认 DB；真实签名安装/Host/来源/预算/真人审批仍不可证明，不能开启自然 worker 或称真实闭环。下一波优先处理当前服务恢复的可验证入口与 Browser gate，若缺可信配置则继续独立首链安全门，不以隔离 PG 冒充真实结果。Prime 远端异步投影状态单列，不作为完成权威。
