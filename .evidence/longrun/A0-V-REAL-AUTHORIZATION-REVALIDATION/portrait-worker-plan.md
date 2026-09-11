# D01阶段Worker

2026-09-11，基线381b1e03，AOS-000573。按231-5画像评审后才下一阶段。

新增 `services/aos-api/aos_api/ecommerce_analyst_portrait_worker.py`：复用既有CanonicalTaorRunner与阶段stop_after_step。校验同scope executing Task/running Run/approved三步Plan原hash/指定D01实例/稳定attempt，要求尚无完成阶段；think读取正式D01统一输入，act再核对运行lineage后调用治理服务，verify读取正式Insight及原attempt产物，observe只留精确insightRef、不留敏感原文；stop_after_step=portrait，不抢诊断步骤、不把整个Run完成。未知结果阻断人工/正式恢复，不自动新建attempt重发。

新增测试：lineage负向与固定attempt、adapter来源/结果校验，隔离正式TAOR调度验证画像边界与拒绝下一阶段。宿主配置、审批与真实质量仍需接续，本模块不自动创建AgentRun或批准画像。无Provider真实调用/主库迁移/push。
