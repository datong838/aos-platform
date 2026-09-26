# W5CB4 P2g｜同一原内容 Artifact 的当前主体 Eval 子证明

- 基线 `m1@dbfc8f42`，先补第五增量文件级方案，仅扩 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`。测试每次克隆拥有者模板，正式 Alembic 升到 `a0v_105`；未迁移当前业务库。Graph、治理/主体 Dataset 与 Suite、治理 EvalRun/报告、ReleaseGate、PublicationEvent、冻结 READY 内容 EvalContract 均通过正式 Store/Service API 在同一隔离库创建，而非直写假报告。
- 原批准 Plan 创建前写 exact `content_review.gateRefs`，再建立原 TaskRun、预算、command/runtime Receipt、受控本地结果、Provider/两条 Usage Receipt、settled Artifact、唯一成功 `content_generate` 四相 StepRun/checkpoint。正式 `AipEvalRunner.run_by_contract` 在原 Artifact、最新成功 attempt、当前合同和同一库主体 Suite 上产生 gate-passed 报告；结构预审 target 消费原可读内容，报告不含正文。另一连接独立核 EvalRun `succeeded`、合同/Artifact/attempt exact JSONB 和唯一 EvalReport。
- 受控 prepare、业务 context、Provider 响应及隔离 Graph target/judge 是明确测试接缝。此证明只到结构预审报告：未证明真实商品事实、真实 Provider、九操作完整 Host 锁/自然 worker、人工 ReviewIssue/ACCEPT、公开 GET 或生产安装。没有商城源读取、旧 12 Run 重放、230 L0 推进或生产外呼。
- 专项分别 `1 passed`（当前合同/原 Plan）和 `1 passed`（同库原 Artifact 主体 Eval）；内容、通用 EvalRunner 与邻近 PG 累计 `294 passed, 35 skipped, 7 warnings`，`git diff --check` 通过。纯后端事务验证，浏览器验收不适用。
- 下一波：让 `ContentReviewPendingReader.read_one` 在**同一**原库/对象上无替身读取稳定候选，逐一验证错合同、旧 attempt、失败/重复报告、已有 Issue/安装漂移失败关闭；只有组合门过关才讨论公开 GET/正式 Issue 创建。
