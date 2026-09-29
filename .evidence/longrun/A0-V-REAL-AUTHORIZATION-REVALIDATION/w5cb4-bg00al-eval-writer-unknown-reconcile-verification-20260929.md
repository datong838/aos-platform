# W5CB4 BG-00al｜Eval writer unknown 提交只读对账验证

方案：`w5cb4-bg00al-eval-writer-unknown-reconcile-plan-20260929.md`；依据 231-5 unknown 先查目标 Receipt、绝不猜测/重发。先写 test-only 真实 PG 专项，模块缺失 RED collection 退出2，再新增只读对账器。调用方必须提供 `aos_runtime`、精确租户、repeatable-read/serializable 且 read-only 的事务；函数取数据库当前 `transaction_timestamp()`，复用 BG-00af 当前持久 authority/Report/双 Receipt/sidecar 全 case reader。仅完整精确证据给 `COMPLETE`，其余 `UNKNOWN`；无 ABSENT 可重发状态、无写表/路由/Host/Gate。

test-only `aos_bg00ad_schema_v2_20260929@a0v114`：BG-00ak 独立登录真签名提交前对账 UNKNOWN、提交后 COMPLETE；只留 Report、跨租户、错误 role、可写事务、错误 input、当前撤销均 UNKNOWN。专项7 passed，相邻累计69 passed，退出0；`git diff --check` 与 `compileall` 退出0。测试 fixture 清理后，test-only 与当前 `aos_current_preview_20260927@a0v114` 六张 Eval 表逐表0行，临时 policy0、BG00ak LOGIN0。当前库未写。

结论限于 test-only 只读对账机制。UNKNOWN 不等于未提交，不能自动重发；现无生产 caller/正式 issuer/Owner/批准/writer ACL/G2 内容/S3/Gate 或自然首链。下一波先只读核正式授权来源和配置缺口，任何当前实例开通仍须独立备份+克隆+零执行窗口。
