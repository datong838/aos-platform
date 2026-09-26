# W5caj｜BG-03 单商品经营方法 Brief 合同核验

方案先行 `bc12c319`；新增文件仅 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/sales_weapon_brief.py` 与 `services/aos-api/tests/test_sales_weapon_brief.py`。没有改 D03 v1 prompt/请求哈希、GrowthPlan DB schema、Host Owner、Review/Handoff 路径或商城数据。

1. RED：新增测试在缺模块时按预期 collection error；补充包/SDK 的精确 PYTHONPATH 后进入实现。
2. 最小实现：不可变 `SalesWeaponBriefDraft` 只允许一项商品来源键、带来源的客群假设与场景、适配/不适配、建议性价值表述、未知事实、禁止表述及真人交接条件；所有声明引用必须属于草稿 exact EvidenceBundle 集，外部引用、重复、空项、错误计划/决策类型、无时区截止面拒绝。`validate_against` 只比较 Host 传入的 exact 引用和观察时间，不读取数据库、不推断证据语义或授权。
3. 专项/相邻累计：新 Brief、旧 GrowthPlan draft/receiver、Review 与内容 workflow 共 **81 passed、1 skipped、7 既有 warnings**；`git diff --check` 与新文件 compileall 通过。跳过项没有被记作通过。
4. 一致性与风险：产物明确 `authority=draft-only`，不持久化、不触发模型/任务/费用；本波仅闭合 BG-03 合同切片。来源引用并不能独立证明商品功效、库存、利润或适用人群，后续 Owner 必须在同租户、当前水位、批准计划下验证并发布；旧已完成 D03 attempt 不得重标为新协议。没有新 UI，本波浏览器验收 N/A，真实 A1 尚未完成。
5. 下一波 W5cak：先查现有 GrowthPlan/四 Artifact/内容 Task 的实际调用点，设计 **唯一** Brief 发布 Owner 和 exact 评审/Handoff 接线；先验证旧 v1 兼容与拒绝矩阵，再最小编码。不得让本合同成为无人消费的第二套计划权威。旧 12 Run 退休仍是独立后置待办，不阻挡无副作用开发。

硬边界：m1 单写不 push；230 L0 挂起；`dev-org` 零 canary；不读商城源行、不重发旧 attempt；真实 Provider/费用/外部动作仍需当前独立授权。
