# BG00GI 首次内容 Action 与预算联合路径

基线 AOS-001049 / m1@56274293 / a0v128。复习 231 总计划、231-5 §1/4/5/6、225、P2g30b 原方案及442。当前真实库只读，独立标准完整迁移库用于开发验证。

## 已定位的阻断与实施顺序

1. reserve 与 ContentBudgetCommandOwner._approved_action 都要求审批 payload.budgetUpperBoundMinor；RETURN 门却用该通用字段单独触发返工分支，违反225“旧首生路径不改”。将识别键集合与精确六字段合同分开：仅排除 budgetUpperBoundMinor 这一已证实共享字段，其他五字段仍触发旧禁入；精确六字段、风险与当前 authority 检查不变。
2. RED覆盖 maker/checker 两个入口的首次预算字段、全部返工标志及组合；R1 首生保持草稿策略，不提升执行权。
3. 独立完整PG中复用GE签名费用批准/低权限消费/派生价格；通过 TaskStore 创建Task/Plan/Run，通过 ActionStore 创建Proposal和独立checker决定。无直接INSERT审批、固定binding hash、price_for或关闭数据库guard。使用真正 reserve 入口验证无ImpactPreview/binding的批准仍失败且零reservation，重复Proposal/决定幂等。
4. 此测试证明公共来源拼接与下一真实缺口，不能宣布完整预留成功。正式初链仍需当前 frozen ImpactPreview/合法来源绑定。发现 ContentBudgetCommandOwner._minimum_bound_fen 明确拒绝 development_cost_authorization，GE风险价还不能进入该Owner；下一波须依231-5未知定价人工风险额度规则修复该接线，不能填零价格或绕过批准。

## 精确文件

- services/aos-api/aos_api/ecommerce_content_repair_action_binding.py：识别键与六字段校验分离。
- services/aos-api/tests/extension_runtime/test_ecommerce_content_repair_action_binding.py：请求/决定/返工未放行回归。
- services/aos-api/tests/aip/test_content_first_action_budget_pg.py：真实Store联合路径及预算无binding负例。
- 本plan与verification；443续接、D-waves、Task/Delivery及AOS/Prime收口。

## 验证与风险

先新测试RED，再最小实现、专项、相邻预算配置/RETURN权威测试。隔离fixture中的身份和Provider前置只是测试依赖，不构成正式身份/自然首链验收；不启Host/Provider、无源读取、无外部请求。纯后端无页面变动，browser不适用。当前数据库不迁移、不重启；代码迁移头保持128。精确add/commit、不push。回滚只需回退本波代码提交，不改现有数据。
