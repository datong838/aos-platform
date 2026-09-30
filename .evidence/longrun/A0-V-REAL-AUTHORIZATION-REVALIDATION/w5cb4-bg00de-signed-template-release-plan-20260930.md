# W5CB4 BG00de｜首链签名职责模板发布合同审计方案

## 上位复习

231-2 §签名发布禁止改已发布内容，候选版本需独立构建/签名；231-1 N0→N8 与 231 总控 §7.2 规定首链只做分析→内容必要切片，不把未证明的模板扩展自动列入前置。BG00dd 只证当前 analyst profile 与 media STANDARD template 不同，尚未证明首链 N8 必须新增 analyst `ResponsibilityTemplateRevision`。

## 文件级只读检查

1. 读 `bundles/candidates/ecommerce/solution.ecommerce.growth/1.11.0/bundle.yaml`、当前已签名同版 production profile/template、`scripts/build_ecommerce_current_candidates.py` 版本选择；确认已有版本和资源类别。
2. 读 `aip_responsibility_template_authority.py` 已安装 active 签名 artifact resolver、`aip_production_contract_store.py` 职责计划依赖；查 231-1 N8 的精确验收动作是否真的要求 analyst 新模板。
3. 不改 `bundles/releases`、当前签名树或当前 DB；若必要性不成立，登记为非首链前置并转更靠近当前安装/Host 门的切片。

## 判据

给出具体 release 版本、artifact 类别、精确缺口与首链依赖结论。无代码改动时 RED/回归不适用；若决定新增候选，必须另写独立版本/签名/迁移方案并在 test-only RED 后实施。
