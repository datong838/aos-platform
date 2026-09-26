# W5cak｜BG-03 Brief 接入现有内容 Task 的最窄合同方案

复习 231 A1/BG-03/04、W5caj 和当前代码：`ReviewHandoffRequest`→`ContentTaskSpec`→Host `_strict_review_accept_command` 已是唯一正式内容任务入口；Host 命令字段严格固定，不能擅增 `weaponBrief` 字段或新造 Handoff Owner。W5caj 草稿目前无人消费，因此本波只补**包内 Brief→现有 ContentTaskSpec 的确定性映射**，供后续当前 Owner 在读取已发布/已评审 Brief 后调用；此函数不发布 Brief、不执行任务、不宣称授权。下一波处理权威发布与真实接线，不让纯映射冒充业务完成。

文件级：修改 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_content_campaign_workflow_contracts.py`，新增从 `SalesWeaponBriefDraft` 构造 `ContentTaskSpec` 的函数，仅映射中文业务字段，不把技术商品键、来源 ID 或未知利润当事实；产品、客群、场景、未知/禁说和交接条件必须保留，超出既有 Task 长度上限直接拒绝、不截断。新增 `services/aos-api/tests/test_sales_weapon_content_task.py`，先 RED 覆盖字段保全、exact GrowthPlan 与四 Artifact、空/过长/技术污染拒绝、原 ContentTaskSpec 兼容；复用 W5caj 草稿测试，不改 Host/DB/UI。代码前 hash 以本波 `git show HEAD` 为准。

专项：新测试和 Review/Handoff/内容 workflow/旧 GrowthPlan 邻接累计；`git diff --check`、compile。浏览器 N/A（无新页面）；verification 明确 CODE_ONLY。A0-V 当前授权、源新鲜度、审批、预算、真实 Provider 仍由既有 Owner/正式运行门控制。旧 12 Run 不重发、不读商城源行、m1 单写不 push、230 L0 挂起、dev-org 零 canary。后波必须先把 Brief 保存到既有 Artifact/Plan 权威并读回，再由 exact 评审消费；否则此映射不算可用交付。
