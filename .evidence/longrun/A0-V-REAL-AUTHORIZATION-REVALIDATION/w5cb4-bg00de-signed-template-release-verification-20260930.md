# W5CB4 BG00de｜首链签名职责模板发布合同审计

## 上位复核与结论

231-1 N4 的 BI 编译与 N8 生产合同均引用精确 `ResponsibilityPlanRevision`；`ecommerce_business_investigation_aip_composition.py` ready 要求该 ref 非空。`ecommerce_business_investigation_aip_authority.py` 当前构造 `CreateResponsibilityPlanRequest` 时调用 `published_template_ref("ecommerce.business-investigation.readonly")`；`aip_responsibility_template_authority.resolve_responsibility_template` 对它有本地哈希特例。这是代码级兼容来源，未绑定当前已签名安装 active 的 artifact。因而该依赖**属于首链**，但不能把本地特例当作当前签名来源验收。

## 发布路径事实

`231-2` 明确已发布 release bytes 不得改写；新的 runtime/content 须在候选版本构建、由 release pipeline 核验发布。`scripts/build_ecommerce_current_candidates.py` 固定当前 `solution.ecommerce.growth/1.11.0`；候选目录最高为 1.11.0，当前签名树也是 1.11.0。该版本 `bundle.yaml` 的 `schemas` 资源允许 `content/production-profiles/` 与 `content/media-production-templates/`，但当前已签名资源中无 `business-investigation.readonly` 的 `ResponsibilityTemplateRevision` artifact。把其 JSON 塞进当前签名树或旧版本目录会破坏签名和确切 lock，不可做。

## 下一切片精确边界

BG00df 先写独立候选版本与 artifact 登记方案：用现有六个 `_ROLE_BLUEPRINTS` 及产品 profile 冻结**候选模板字段**，对 schema/gate/assignee 来源逐项核合法权威；test-only 新版本的 manifest/签名/Registry artifact 与 resolver 负例必须先 RED。生产 materializer 由本地特例迁到当前已安装签名 ref 的切换需独立兼容/回滚测试，不能在当前实例未安装新版本前直接删除旧分支。不得修改当前 1.11.0 已签名树、当前库、旧 Run 或商城源；不能为首链伪造六 active AgentInstance。

本波只读审计，无代码修改，RED/回归不适用。当前正式 Host/三身份/assignment 仍缺，首链 pending。
