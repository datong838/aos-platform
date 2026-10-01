# BG00GW-d accepted草稿到approved后继来源关联

基线AOS-001068 / f15c3455；承接461/231-1 N5/231-5 exact审批。新签名协议仍待裁决，不在此波实施。

## 文件与合同

新增services/aos-api/aos_api/ecommerce_analyst_stage_handoff_source.py：只读、事务绑定来源读取器。输入HostTransaction/可信scope、approvedRef、decisionRef及上游预期taskRun/Plan/stageAttempt。复用原ReviewAdvanceHostService._revalidate_growth_plan锁当前approved和原Receipt，原Owner.get_plan_exact取historical draft，原StageDecisionStore.read_current锁当前决策，原require_stage_decision_applicable检查有效accept及精确输入。
approved.priorRef必须等于决策评审的draft，draft.lifecycle=draft、approved相邻版本，剔除既有批准元数据后全部业务字段必须相同（包括生成artifact、来源decision、salesWeapon）；原draft generation artifact必须非空并等于决策artifact。不把历史draft必须current作为条件，因为原approve已使其成为历史。两项批准必须均已发生且accepted未过期；不强加两项批准相互先后。
返回三份Owner校验后的来源对象，不含allowed/gatePassed/任务创建，也不签名。尚不接入旧OPENIssue消息，不改变它的授权语义。后继真正Handoff必须复验当前签名评测、原职责/来源/安装fence、授权及预算，不能把此来源结果当许可。

新增tests/extension_runtime/test_analyst_stage_handoff_source_pg.py：标准全迁移一次性PG，显式fixture草稿/决策经原Owner，原approve后继；读函数无mock。正向关联、反向错误run/hash/租户、过期/撤销、合法Owner写入但更换内容的后继拒绝。测试初始对象不代表模型自然生成或人类HTTP授权；不得声称自然首链。

## 步骤/风险

先缺模块RED→最小只读实现→专项与原批准来源/决策规则累计→compile/diffcheck→复审证据→m1精确提交→AOS/Prime/462/D-waves。无UI浏览器不适用。
锁顺序approved head→stage head，后续Handoff调用须同顺序；当前函数不写入，不启Host/worker/Provider，不访问当前真实库。回滚仅两个新源/测试文件；真正执行接线仍需完整生产者与授权验收。
