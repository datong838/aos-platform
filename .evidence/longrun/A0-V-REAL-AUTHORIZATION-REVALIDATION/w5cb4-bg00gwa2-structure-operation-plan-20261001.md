# BG00GW-a2 原结构评测运行消息接线

AOS-001065 / m1 4b1d5dec；承接458及231 A1、231-1包边界、231-5阶段评审。Task W5CB4-BG00GWA2-STRUCTURE-OPERATION-20261001。

## 已读事实

包 `analyst_structure_eval.evaluate_structure` 能按原文本检查画像/诊断/方案结构；`analyst_structure_case.structure_case_from_query` 能从原生成query校验并推导来源规则。但包 `__init__.handle` 仅注册了 derive_structure_case，没有结构评测调用消息。现有测试仅直接 import 函数，不能证明原 package dispatch 能执行它。
原 compile-only Handoff 也仍要求四类业务 Artifact，不能用它绕过457登记的决策来源错位。

## 文件与最小实现

- 修改 `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/__init__.py`：在已有 ecommerce_growth_analysis_advance 下分发固定 kind=evaluate_stage_structure；不增 operation/路由/权限。
- 新同目录 `analyst_structure_eval_operation.py`：只接受 kind/stage/query/subjectArtifactRef/subjectText 五键；用原 query deriver 构造原 text-subject envelope，调用原 evaluate_structure。不能接收客户端 sourceCount、caseInput、passed、Gate或模块路径。错误不回显 query/原文。
- 新 `services/aos-api/tests/extension_runtime/test_analyst_structure_eval_operation.py`：通过 package.handle 验证三阶段原prompt派生规则＋原文正/负结果，原文hash、额外字段、错误operation/kind、数据不变及错误脱敏。测试来源是显式fixture，仅证明消息接线与确定性算法。

此内部无IO消息复用已实现算法，不改签名用途或评测准入语义。结果只含既有 structurePassed/detailCode，不返回审批、执行许可或正式Report。Host未来必须核实query/text属于同一当前generation，并把完整输入绑定正式签名；本实现不承担该权威。

## 执行与退出

先通过原 dispatch 运行新测试得到 RED，再加最小消息adapter。专项＋原structure/case/proposal/review消息累计回归，compile/diffcheck，复审语义边界。无页面变更，浏览器不适用。
只提交本波路径，生成制品/签名/当前安装不改，不部署或启Host/worker/Provider；不读商城源，不访问当前真实库。本波不宣称OCI或自然首链验收。回滚仅此三个代码/测试文件。
完成后更新AOS/Prime/459/D-waves，立即回到完整签名输入合同与原accepted阶段决策→Handoff的设计。GT与正式OIDC/API身份问题独立待答。
