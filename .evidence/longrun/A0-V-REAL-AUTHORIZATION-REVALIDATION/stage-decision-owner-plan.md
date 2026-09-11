# 阶段决定不可变Owner与隔离迁移

2026-09-11，基线e8fff35d，AOS-000573。仅内部领域Owner，后续人类职责/当前Eval与产物核验服务才是业务入口。

新增 `services/aos-api/alembic/versions/a0v_014_analyst_stage_decision.py`，接a0v_013：领域head/revision两表，复用analyst authority receipt，租户复合PK/FK、父修订、deferred receipt FK、FORCE RLS、runtime SELECT/INSERT和head UPDATE最小权限，显式REVOKE默认继承权限，历史update/delete/truncate触发拒绝，forward-only保留历史。主库012不迁移，只在一次性clone按012→013→014测试。

新增 `services/aos-api/aos_api/ecommerce_analyst_stage_decision_store.py`：显式HostTransaction/scope，复用TransactionBoundConnectFactory+既有Owner._publish，不自行commit。固定目标（run/plan/stage/step/subject/artifact/eval）计算decision_id，单目标单head；双advisory锁保护target及idempotencykey，实际canonicalhash、actor/time、prior exact、同目标不变、expectedVersion CAS；初始不得revoke，后续可明确再决定或撤销，所有历史可读。read_current必须引用当前head，历史accept不能越过后来revoke继续适用。Receipt重放不意味着当前可执行。

新增测试：幂等、冲突、撤销使旧current失效、外层回滚、并发唯一、runtime RLS/权限/历史不可变、目标漂移/时钟/伪hash拒绝。Owner不自证human身份或Eval通过，不安装到宿主执行；下一波正式身份与阶段来源读取再接产品review命令。
