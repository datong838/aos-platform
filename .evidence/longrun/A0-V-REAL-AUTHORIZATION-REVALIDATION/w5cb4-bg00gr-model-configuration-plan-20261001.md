# BG00GR 模型合法配置来源联合

基线97642c33 / AOS-001058；Task W5CB4-BG00GR-MODEL-CONFIG-20261001。
复习231-5与AIP 22号exact模型路由Provider-Eval方案：配置可保存、外部unknown禁入、原Eval唯一权威。

## 本波缺口

RegisteredModelRevision、ModelRouteRevision即使draft/validated也强制非空evalGateRef。既有测试使用test:eval占位，真实配置尚未评估时无法诚实保存；禁止补假通过Gate/Health。
最小增量：这两个合同仅draft/validated允许null或缺省Eval；其余生命周期仍要求exact ref。active原Store继续require_exact_passed。中央Eval reader遇None给既有DependencyBlocked而非AttributeError；SDK解析与现有页面空态一致。
已有非空payload/哈希不变；null是新配置的显式缺失，不新造Eval表/模型真源，不改变审批、预算、容量或Provider调用授权。

## 文件级顺序

1. tests/aip/test_aip_model_runtime_contracts.py、apps/web/src/api/aipModelRuntime/parser.test.ts：RED覆盖诚实draft/validated缺失与active禁入。
2. aos_api/aip_model_runtime_contracts.py：可空声明与生命周期/类型约束；aip_eval_authority_store.py：缺失稳定拒绝；routers/aip_model_runtime.py：overview缺失Eval不能异常或空集合误判通过。
3. apps/web/src/api/aipModelRuntime/{contracts,parser}.ts、pages/s2/aip.tsx：nullable解析与未评估展示。
4. tests/aip/test_formal_model_configuration_pg.py：实际签名Provider/费用派生/Quota/Network经原Model Store形成无伪造Eval的配置；原resolver及HTTP overview必须BLOCKED，active/model_copy旁路均拒绝；不补Health或Eval。
5. 后端相关累计、前端parser/类型与适用浏览器，review/verification/精确提交/AOS及Prime/D-waves同步。

## 风险与后续

类型检查确认ModelCatalogPage.tsx已有可空显示，但内部CatalogModel只允许undefined。新增独立CATALOG Task，将该投影字段扩为null | undefined；不制造引用、不改渲染路径。

浏览器复审发现路由页把validated标成“已批准版本/exact Eval批准”，与无Eval配置合同不一致。沿现有页面改为已校验配置、运行前仍需评测；UI-REVIEW Task覆盖原交互测试及空Eval历史渲染。该文案不授予运行权。

检查所有eval_gate_ref调用方，执行入口须已有active/resolver门；缺少门则本波修复或追加scope后修复。历史非空引用/哈希与阅读必须保持。
本波不产生真实Eval结果，不连接Provider。实际模型评估须原Runner+真实执行器+Report+ReleaseService.derive_gate，不能直接append伪造passed。
真实实例仍只读、未重启/迁移；230 L0/旧12Run/手工run_definition边界不变。后续原Review/AgentRun/首生审批/Capacity/GE held及自然首链仍待证明。
