# W5CB4 BG00dd｜首链职责计划合法来源审计方案

## 上位与边界

按 231 总计划、231-3 安装/配置顺序、栖月汇产品方案和 E17-w 八候选来源，复查当前已签名 growth 包的职责模板与 production profile、`CreateResponsibilityPlanRequest`/Store 正式依赖、当前库候选。目标是拆分可从产品制品读取的字段与必须由当前人/系统授权形成的字段，不创建当前职责计划、不借旧本地模板替代签名安装。

## 文件级检查

- 只读 `signing-state/signed-bundles/solution.ecommerce.growth/1.11.0` 下已签名 `standard.responsibility.json` 与 `production-profiles/ecommerce.analyst.json`；签名真实性先由 BG00dc 当前 receipt preflight 核验。
- 读 `aip_production_contracts.py` `ResponsibilitySlot`、`CreateResponsibilityPlanRequest`，Store 的 template/profile/assignee 精确依赖和 `aip_responsibility_template_authority.py` 解析边界。
- 当前库 `conn.read_only=True` 核职责计划、推荐、确认、合并策略、assignee Receipt 与 AgentInstance 状态；只读精确租户。

## 预期输出

列出模板可继承字段、不能猜的 schema/gate/assignee/治理字段；明确模板是 media-studio STANDARD 而 analyst profile 是不同合同，不混用。指出现有兼容本地模板与当前签名安装的差异，给出下一波独立最小代码切片。无代码改动时 RED/回归不适用。
