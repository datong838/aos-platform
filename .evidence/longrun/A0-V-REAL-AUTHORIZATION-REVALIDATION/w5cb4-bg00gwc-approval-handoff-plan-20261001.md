# BG00GW-c 原批准到Handoff来源联合验证

AOS-001067 / 075193f4；依据231-1 N5、231-5审批绑定与Receipt、460。
原批准服务生成draft相邻approved版本；原ReviewAdvanceHostService._revalidate_growth_plan按当前head和原OwnerReceipt验证approved。旧单测monkeypatch此校验，尚不证明两端兼容。

本波只新增 services/aos-api/tests/extension_runtime/test_growth_approval_handoff_source_pg.py：标准全迁移临时库内，显式fixture草稿经原publish_plan落库，原approve创建后继，再原Host来源reader回读。断言原Receipt、重复批准幂等、草稿变历史、错租户/错hash/旧版本拒绝。覆盖原路径现状，无行为新增，所以采用特征验证，不人为制造RED或改生产代码。
租户org-org/dev-project；dev-org仅只读负例；禁止修改当前库/启动Host/Provider。fixture初始draft不是原模型生成，也没有真人HTTP鉴权或阶段Eval，不宣称自然链。调用私有来源reader只能证明该段，不能称完整Handoff通过。
该证明用于明确后继接线：accepted decision仍需绑定被评审draft，approved.priorRef必须精确指回该draft；旧OPENIssue和四Artifact条件仍未解决，禁造行跳过。发现原合同不一致先定位再修计划，禁止顺手开放新用途。
执行：针对性真实PG→累计原approval与review/package回归→compile/diffcheck→证据→m1精确提交→AOS/Prime/461/D-waves。无UI变更，浏览器不适用。
