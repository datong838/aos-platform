# W5CB4 P2f-b 第 1/4 步｜内容预审草稿 Graph 代码门

## 结论与边界

- 按已提交方案 `677841ed` 增加确定性、无 effect 的内容人工评审前完整性 Graph；仅证明隔离代码可表达正文、商品/渠道、来源、约束核查的存在性，不声称事实正确、内容合规或人工评审通过。
- Graph 仍为 draft、`persisted=False` 的测试快照。生产当前无 `ecommerce_content` 正式 Suite/READY Contract；无发布、无元库迁移、无 Worker/Provider/商城源读取、无旧 Run 重发、无新 Plan gate 绑定。

## RED→GREEN 与专项/累计

- RED：先加入测试，缺少 `aos_api.ecommerce_content_pre_review_eval` 时按预期 `ModuleNotFoundError`。
- GREEN：`test_ecommerce_content_pre_review_eval.py` 共 5 例，覆盖确定性正例、空/缺字段、错误封套、空白正文/错类型/错 Artifact ref、Graph 篡改拒绝。
- 邻近累计：内容 Review authority、TaskRun Owner、内容 Eval input 与 Logic dry-run 共计 `50 passed`；`git diff --check` 通过。无页面改动，浏览器验收不适用。

## 复审与下一步

- 与 231-5/231-9 的人类 exact 评审边界一致：此 Graph 不批准事实/合规，只是进入人工评审前的结构门。`AipEvalRunner` 仍独立校验 Artifact 哈希、内容来源及最新 attempt；代码 helper 不能代替正式 Subject EvalRun。
- 第 2/4 步建立隔离 PG 的 Suite、ReleaseGate/Publication、冻结 READY 内容 EvalContract，正反证明正式权威；在完成前 P2f-b 未完成，首链不得写为 GREEN。
