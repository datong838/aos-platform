# W5CB2-P2c｜单次 Host 提交与独立读回代码门

- 基线 `d47d5c05`，承接 P2b exact 预检/Journal hash 修复。此处为代码门，**不是**生产预算命令或可读产物验收。
- 在 `a0v_104` 唯一 claimed token 下重新预检当前 Review/Task/AgentRun/Route/批准/容量/安装组；只调用一次正式 capability `LockedEcommerceGrowthHostPort.commit`。Port 原事务完成锁定、12 Ref revalidate、预算 HELD、Journal PENDING、Runtime Receipt 核对与提交；Owner 不发 Provider。
- Host 返回后另开只读事务，要求同键/同租户预算 HELD、预算请求 hash、不可变 Journal 完整命令 hash、Runtime Receipt 完整命令 hash/原代次/原 response 均一致，且 Provider 调用数为零。只有独立读回通过才调用 `a0v_104` ack，再独立读 accepted。超时或读回不明保持 claimed，不补发。
- `main.py` 增加 `AOS_ECOM_CONTENT_BUDGET_COMMAND_WORKER_ENABLED` 入口，缺省 `false`；显式启用仍需 ACTIVE Runtime Host 与 runtime-only DSN。Provider Worker 独立保持缺省关闭；未启当前生产入口，未执行生产迁移，未读商城源，旧 12 Run 未动。
- RED：execute/unknown/default-off 测试先因方法或 Worker 缺失失败。GREEN：Owner 12 项邻近、隔离 PG/预算/Journal 等组合 **66/66**；`alembic heads=a0v_104`，compileall、`git diff --check` 通过。测试专用 PostgreSQL 容器已停止。浏览器验收不适用：无页面改动。
- 证据边界：成功预检、单次 Host 提交及读回的 Owner 单元测试采用受控假权威；隔离 PG 覆盖底层 ack/租户和公共预算/Journal 合同，但尚无**同一真实 schema** 的 Handoff→Plan/Run→AgentRun→容量→预算完整夹具。生产安装/审批/价格/来源是否齐备也未证明。不得把本代码门记作自然首链或 W5CB2 完成。
- 下一阶段 W5CB2-P2d：补完整同库夹具及拒绝矩阵，复审默认 Worker/旧代/未知结果；若全绿，写 W5CB2 完整 verification，m1 提交并同步 D-waves/AOS/Prime，再进入 W5CB3 Provider/MeasuredUsage/可读 Artifact。若真实实例缺合法 authority，只阻断实例，不重发或伪造。
