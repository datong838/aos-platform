# W5caj｜BG-03 单商品经营方法 Brief 合同方案

## 上位与当前缺口

231 A1-01/03/04、231-9 §2/4/7 和双侧增长产品方案 §8 要求一个真实商品×有依据的客群假设×明确场景，明确适合/不适合、证据、未知和禁止表述，并在 exact 评审后交内容任务。当前 `GrowthPlanRevision` (`services/aos-api/aos_api/ecommerce_analyst_authority_contracts.py`) 及 D03 proposal (`.../ecommerce_analyst_growth_plan_draft.py`) 仅有泛化 objective、constraints、item/evidenceRefs；`ReviewHandoffRequest` 已有 exact GrowthPlan/四 Artifact 和内容任务，但没有结构化销售武器包方法 Brief。本波**只补包内可验证业务合同**，不改既有 v1 D03 prompt/哈希、DB schema、Host Owner 或审批/执行路径；后波把合同接到真实生成、权威保存、评审和 Handoff。

## 文件级清单

- 新增 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/sales_weapon_brief.py`：不可变 `SalesWeaponBriefDraft`，带 exact GrowthPlan/Decision/Evidence 引用、商品标识、客群假设、场景、适配/不适配、证据绑定的主张、未知事实、禁止表述、交接条件与来源截止面。它只检语法、数量、引用闭包和跨对象一致性，**不能把 exact ref 冒充语义证明或当前授权**。
- 新增 `services/aos-api/tests/test_sales_weapon_brief.py`：先 RED，覆盖一商品一场景、至少一项不适配/未知/禁止表述、主张必须绑定可列出的来源、重复/外部证据拒绝、错误 resourceType/hash/时区拒绝、截面未来时间拒绝、序列化稳定。使用包源码测试，无需 PG/Provider。
- 不修改 `ecommerce_analyst_growth_plan_draft.py`、`ecommerce_analyst_authority_contracts.py`、`ecommerce_business_investigation_review_command.py`，避免旧 D03 请求哈希/已批准 Plan 漂移；后波接线方案需另立并先验证旧版本兼容。

## 执行和退出

方案先提交→RED→最小代码→专项与已有 GrowthPlan/Review/Handoff 邻接累计→代码/方案一致性复审→verification→m1 提交→AOS/D-waves/Prime 接续。包内合同通过只算 BG-03 的代码切片，不算真实商品已选、不算 GrowthPlan 已批准、不算内容产物或 A1 自然成功。浏览器无新入口，本波记 N/A，后波接入后验收。商城源行不读，原 12 Run 不重发；dev-org 零 canary、230 L0 挂起、不 push。
