# W5CB4 P2g17：Task Cockpit 三段反馈只读权威视图验证

日期：2026-09-27。方案先行提交：`476674c9`，对应 `w5cb4-p2g-content-subject-eval-review-pending-plan-20260927.md` 的第十七增量。此文件记录本波代码和隔离验证，不宣称当前实例已自然完成真实首链。

## 文件范围与结果

- 新增 `services/aos-api/aos_api/ecommerce_workshop_feedback_read_contracts.py` 和 `ecommerce_workshop_feedback_read_model.py`：按租户的 repeatable-read/read-only 快照、最多 20 条原 ACCEPT 命令、固定 cutoff/排序；依原反馈 port、三个目标 Receipt、原 Artifact/Run 与正式 EffectReview 读回组成中文业务层和折叠审计字段。`pending` 候选与正式 Wiki 入库分开，`insufficient` 只显示“证据不足”，执行授权恒为 false。
- `services/aos-api/aos_api/routers/ecommerce_workshop.py` 仅增加 GET `/v1/ecommerce-workshop/views/task-cockpit/feedback`，沿用现有 Task Cockpit 安装与主体租户门。无写命令、无新表/迁移、无商城源读取。
- 新增 `tests/extension_runtime/test_ecommerce_workshop_feedback_read_model.py`，扩原同库链 `test_ecommerce_content_review_pending_pg.py` 和 OpenAPI 冻结清单测试；原其他功能未改。

## 可复核检查

- 新 DTO/路由专项及同库链通过；同库链验证第二段已接收而正式效果尚未形成、正式效果“证据不足”但候选尚未形成、三段全接收，及原 Run 被改回 running、第二目标 body 漂移后拒绝展示；`dev-org/dev-project` 读出零项。
- 累计命令：`uv run pytest tests/extension_runtime/test_ecommerce* tests/aip/test_aip_memory_store.py tests/test_ecommerce_workshop_api.py tests/test_ecommerce_workshop_task_cockpit.py -q`，结果 **1024 passed, 191 skipped**。补充原同库链 Run 非终态反证后重跑该文件：**7 passed**。
- `git diff --check` 和新模块 `compileall` 通过；Alembic 未新增迁移。浏览器验收本波不适用：只提供后端 GET，页面接线是下一波。

## 边界与后续

- 只读历史呈现不是当前执行许可；当前实例新反馈 worker 仍默认关闭，没有触发 Provider/外发、旧 Run 回放、手工 `run_definition`、微商城源读取或 Wiki 发布。不能以隔离 PG 绿称真实业务首链已自然完成。
- 下一波 P2g18：前端 Task Cockpit 追加三段来源卡、失败/空态与审计折叠，使用真实浏览器验收；先提交文件级方案，再最小编码和复验。可交给其他开发的是独立 worktree 的页面/只读测试，m1 仍由唯一集成写者串行提交，避免与本波文件冲突。
