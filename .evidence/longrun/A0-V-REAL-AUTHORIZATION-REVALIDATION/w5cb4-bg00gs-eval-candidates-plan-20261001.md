# BG00GS 原模型配置到评测候选产品接线

基线49f7e650 / AOS-001059，Task W5CB4-BG00GS-EVAL-CANDIDATES-20261001。
复习231-5、AIP22 exact模型运行方案、452接续。原/v1/evals/run仅Logic；签名Skill Eval执行证明合同不支持Model target，不能借用为合法模型执行。真实模型执行/费用/出境/secret授权尚未齐备。

## 事实与增量

EvalsPage目前从旧model-admin目录失败后回退发现目录；不是不可变Model/Route authority，也没有排除evalGateRef循环引用的候选hash。新端点只读返回当前draft/validated的sourceRef、expectedHeadVersion及下一active revision的targetRef。候选hash复用evaluation_candidate_ref，改版后仍须重新读取并CAS；该投影不授予执行权。
不新建Run/报告/Gate/健康，不调用Provider，不把配置检查当质量Eval。页面显示“需独立执行”，禁止旧目录fallback。

## 文件级实施

1. tests/aip/test_formal_model_configuration_pg.py补原HTTP端点RED：读取签名来源构成的Model/Route，对比next-active语义hash、原sourcehash、head版本；再次读取无新增Receipt或Run。
2. aip_model_runtime_contracts.py新增严格只读DTO；aip_model_runtime_store.py单SELECT/UNION同快照读当前head，回验canonical hash与租户，计算下一active target；routers/aip_model_runtime.py注册GET /eval-candidates，Principal scope。
3. apps/web/src/api/aipModelRuntime/{contracts,parser,index}.ts接原端点，严格正整数版本/类型/hash/source-target一致性与executionAllowed=false。
4. pages/s2/aip.tsx评测清单改用SDK只读候选，区分模型/模型路由；EvalsPage.test.tsx与parser.test.ts覆盖无回退和不执行。
5. 后端相关累计、前端/tsc、BrowserPilot只读页面与截图；review/verification/精确提交/AOS/Prime/D-waves。

## 验收与限制

新候选必须source与target同id/type、target revision=source+1，target按active语义生成而非直接拿validated hash冒充将来运行评测。expectedHeadVersion仅观察，未来消费必须重验；响应executionAllowed固定false。无secret字段。
当前API尚未reload时新端点可能404；页面须明确缺证不伪造候选，不为本波强启当前实例。恢复/迁移另波，真实库只读。模型正式Eval执行、自然首链及八场景仍待完成。

## 回归发现与最小修正

2026-10-01累计63项中62通过、1失败：头推进测试仅增加revision，违反原模型同ID/content_hash唯一约束（revision不进入内容hash）。保持原约束，测试改为缩小配置contextWindow并按原canonical规则计算hash，再通过原publish_model推进head；验证刷新后的source/target同时替换旧候选。此变更仅发生在隔离测试库，不改变当前模型能力或真实实例配置。
