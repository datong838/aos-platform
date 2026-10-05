# 完整命令 Health 消费修正

2026-10-05 12:29，完整 Task w5cb4-e17-b90-full-evaluator-implementation-20261005 ACTIVE，租约18:00。基线704fb444/Authority1332；当前142不迁移、不启动业务。

修改完整命令原模块 aip_binding_formal_evaluator.py 和原专项 test_binding_formal_evaluator_pg.py，均属已登记范围。正式消费者必须 native psycopg/dict_row/SERIAL/双身份 evaluator、正向固定tenant及原GUC；拒任意模拟连接。原共享epoch函数别名取值，不直接查epoch表。先协调同Provider ID所有revision写者，再读该ID最新两条观测；最新错exact ref拒绝，不回退较老healthy。严格重新解析FormalExactRef，不能接受缺revision/hash或model_copy绕过。时效用取得锁后的PG clock_timestamp，不用本地时钟或朴素时间强转UTC；原表时间必须aware且 observed_at<=checked_at<expires_at。记录checked_at供后续整个命令统一截止窗，不新增权威表或返回启动权。状态保留原healthy/degraded/unavailable/unknown供原Resolver判断，不能把存在观测等同健康通过。

RED/真实SCRAM隔离5433：原字典结果读取正向、最新错revision/hash、同时间歧义、未来/到期、缺观测、缺精确ref、canary/native非专用身份。夹具原健康表维护插入只是故障输入，正向仅证明事实读取，绝不声明八事实READY；finally专用角色恢复NOLOGIN。专项和现有Health fence相邻串行运行，原40001不包装不重试。完整命令/API/原三写仍是整体Task退出要求，本段不得单独把Task置DONE。
