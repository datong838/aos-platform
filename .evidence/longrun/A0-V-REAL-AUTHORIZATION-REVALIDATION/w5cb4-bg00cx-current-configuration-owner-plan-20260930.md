# W5CB4 BG00cx｜当前配置与 Owner 来源核验及职责空态修正方案

## 上位合同与当前事实

- 231、231-1/3/9 要求当前安装、四源有效期、正式产品恢复入口；空配置和缺授权时保持禁入，不以脚本、历史快照或可点页面冒充首链。
- 当前 `m1@ee5b1c54`、库 `aos_current_preview_20260927`、迁移 `a0v_118`。仅以只读事务核验 `org-org/dev-project`；不读商城源，不写当前库或 `dev-org`。
- 当前八类有效配置候选均为零，operation/binding/assignment 均为零，Owner 成员数为一。职责计划 head、阶段模板 head、档位确认及运行/预算相关 head 也为空；六个 AgentInstance 记录不能替代职责模板、档位治理或合法计划。

## 文件级最小改动

1. `apps/web/src/pages/s2/ProductionContractsPage.test.tsx`：先把零职责计划空态改为精确断言：只报告本租户无计划，提示模板、档位治理、assignee 的正式来源要求，并断言没有创建/运行捷径。
2. `apps/web/src/pages/s2/ProductionContractsPage.tsx`：只修正当前错误的“职责模板权威未接入”静态文案。后端 `routers/aip_production_contracts.py` 已注入 `resolve_responsibility_template`，不能继续把它说成未接入；但不声称当前模板/治理来源已经齐备。
3. 本波不改后端合同、配置候选 SQL、Store、迁移、当前库或 Host。职责计划真正创建需要独立波读取正式模板/治理/assignee 精确来源并通过产品入口，不能在本波补造记录。

## RED、GREEN 与退出条件

- RED：前端空态测试要求新文案、拒绝过期文案，先确认失败。
- GREEN：只改一处静态空态，专项页面测试、相邻安装/配置页面测试、TypeScript、diff check 均退出零；复审 231 的禁入和当前库只读状态。
- 如模板来源或正式 Owner 不齐备，登记精确缺口并转下波产品来源准备，不降低 active、审批、预算与 Host 门。
