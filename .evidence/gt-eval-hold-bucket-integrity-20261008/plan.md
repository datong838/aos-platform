# Eval 已有预留共享桶一致性修复

Rules：231/已批准原生隔离研究/m1单写；先原native RED后精确Task/最小产品变更，正式库只读，无部署/Provider。HEADa7935cc9完整hash修复仍保留。

原生RED：新合法隔离申请/独立审批下，runtime INSERT准确完整hash hold但无bucket links，原hold返回成功，DID NOT RAISE；ROLLBACK后独立0行。

精确修改 services/aos-api/aos_api/aip_model_eval_budget_reservation.py，existing完整hash验证后增加同SERIAL连接只读三桶join校验：恰3kind（PK已有约束）、精确tenant/reservation、currency、reserved=upper、held>=reserved、task model-eval/request与daily/pilot当前BudgetRevision账号准确；period关系由原FK精确join。不创建/修改bucket，不加新行锁，不改变新hold预算算法/审批/费用门。历史period保持原link，不以当天重算破坏跨日合法replay；不是全账本风险证明。

本Task证据中冻结原完整prefix与fresh claim，在新随机保留全迁移DB验证准确hold及replay、缺links拒绝、已有3links但held金额被测试窗口降为0的拒绝。所有窗口rollback。完整hash坏输入也保留负门。专项native后相邻50回归，独立只读回读4表0/exposure0，代码/方案自审，精确m1提交及Delivery/context。浏览器无UI改动不适用，不称独立模型review PASS。
