# 完整共享父风险计划与原生双父读者

承接1608及1668实际五变体对账。基线afc773203/AOS-001669。原typed-proof与atomic Task同owner、原scope内协同单写，不新writer、不动migration。

修改精确文件：`services/aos-api/aos_api/aip_model_eval_execution_contracts.py`（typed Task）；`services/aos-api/tests/aip/test_model_eval_execution_contracts.py`（typed Task）；`services/aos-api/aos_api/aip_model_eval_execution_owner.py`（atomic Task）；`services/aos-api/tests/aip/test_physical_capacity_occupation_pg.py`（atomic Task）。证据分别进入原Task目录。

新增明确v3共享父风险计划，保留原申请/批准/Rule/Suite/完整有序case×purpose、治理、身份描述及唯一Intent引用，金额仅来自两原parent上界。每腿不得传allocationUpperBoundMinor或budgetAllocationRef；不能为旧v2校验内部填1/5/10。joint/Intent引用仍描述，不是已提交事实。共享父计划不得被旧v2签名函数误接纳；新签名/持久producer/共同提交门尚未接入，不在本波伪称完成。

抽取原Owner实现为内部共同原生读者，旧公开方法仍只接受v2，新公开方法只接受v3；两者同样实际读取精确当前父/原申请/审批/费用/锁后期限。每purpose始终父风险10，不按case乘10，也不按每腿均分。原ordinary结算隔离与Source拒绝门不变。

RED：共享计划解析/原Owner入口不存在。最小实现后运行完整契约相邻累计（含旧签名、非法构造）；新共享计划漏case、跨parent/governance、任意allocation、伪执行字段、重复Intent、跨域拒绝；原native完整Suite同caller生成两个批准父，新增方法实际接入验证，callerrollback及独立父记录0。实验 fresh库只供本次native，无正式DB/Provider。

退出范围：完成共享风险计划和原生必要reader接入。尚需原private prepared_plan_risk→v3完整绑定、签名域/可信root、实际token/占用、共同finalizer/Source提交尾部协议、真实transport/Usage及报告。不交完整Task Delivery，不把此必要步骤定义为Goal成功。
