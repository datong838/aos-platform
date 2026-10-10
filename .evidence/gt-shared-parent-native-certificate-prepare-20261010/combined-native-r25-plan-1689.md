# R25 原计划引用修复与完整矩阵接续
Rules：231/joint §11.3、AOS-001689，m1唯一writer、原Task10/Task3证据scope。十Task已同owner续租，无重叠。
R24 terminal23514 CAPACITY_PLAN_REPLAY_CONFLICT；独立READ ONLY确认所有风险与metadata为0，仅预发布Root1，12源hash未变。原prepare_shared_parent_risk_description已经按manifest.executionId建立原planrisk。新增helper随机第二planId违反同请求唯一计划，不能修改产品防重规则。
候选一：完整组合准备矩阵（当前批准原合同，依赖新实验Source/证书/原计划）；候选二：真实Target结果到Judge producer（依赖后续正式合同及结果，不能伪造）。先候选一。
精确文件：本Task/native-r25/combined_prepare_trial.py、source_newjudge_native_trial_1606.py、run-native-r25.py及只读复制fixture/结果；Task3新label shared-native-combined-preparation-1689-r25。新数据库、新Root/新审批、不重跑R24、不延长旧期限。仅helper传入description.plan_id并断言原fact.planId相同，保持全矩阵/所有guard/DML20拒绝/实际COMMIT拒绝及相邻Source验证。签名helper和实验输入精确hash在启动前冻结。无产品代码变动，无正式库、Provider、业务执行或完整Delivery。
