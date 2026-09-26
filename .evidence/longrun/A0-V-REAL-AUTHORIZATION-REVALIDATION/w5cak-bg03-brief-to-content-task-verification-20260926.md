# W5cak｜BG-03 Brief→既有内容 Task 映射核验

先行方案 `c82b646a`。本波只改 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_content_campaign_workflow_contracts.py` 并新增 `services/aos-api/tests/test_sales_weapon_content_task.py`；未改 Host 的严格 review 命令、DB、Provider、UI 或商城数据。

1. RED：新增测试因缺 `content_task_from_sales_weapon_brief` 导入失败。GREEN：从 W5caj 草稿确定性构造既有 `ContentTaskSpec`，保留商品标签、客群假设、场景、适配/不适配、待评审主张、未知、禁说及真人交接；技术商品来源键不进入面向业务的任务文字。超既有标题/目标/约束上限不截断，直接拒绝。
2. 新任务仍携同一个 exact GrowthPlan 与四 Artifact refs；现有 `ReviewHandoffRequest` 对合法中文任务可生成原命令，`API` 技术污染仍由原 review 门拒绝。没有新增 Host 命令字段、第二套任务 Owner 或旧 v1 schema 变化。
3. 新 Brief、新映射、旧 GrowthPlan draft、Review/Handoff、内容 workflow 累计 **70 passed**、7 既有 warnings；`git diff --check` 与 compileall 通过。无新增页面，浏览器 N/A。
4. 关键限制：纯包内映射**尚未接真实 Brief 发布/读取 Owner**，不会自动创建内容任务；`draft-only` 不是已批准商品方法，不证明证据语义/新鲜度。下一波 W5cal 必须找到已有四 Artifact/growth_plan 的权威发布与读取入口，把 Brief 作为已审查内容接入且维持旧 v1 回放；若接口缺口超出窄改动，先方案再编码，不用假入口代替。

A0-V/真实 A1 仍冻结；原 12 Run 正式退休后置但不重发；230 L0 挂起，`dev-org` 零 canary，m1 单写不 push。
