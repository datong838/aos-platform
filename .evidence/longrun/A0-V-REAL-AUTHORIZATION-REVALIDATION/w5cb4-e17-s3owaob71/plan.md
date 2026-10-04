# b71 可变来源epoch隔离候选演练

上位231/BIND-1、b70 plan/两RED；基线c156d3cc，authority AOS-001329；新thread唯一写者。

仅改原两测试文件。在disposable aos_test_*_ti4_test新增随机名临时epoch表，exact tenant/bundle/revision/hash PK、epoch整数初值0、FORCE RLS；没有生产迁移/表/Store变更。opt-in AOS_B71_LICENSE_EPOCH_FENCE仅配合b70两个顺序。受限definer最小SELECT与UPDATE(epoch)用于FOR SHARE锁，调用者仍没有权限；命令锁序Installation→Registry→exact epoch→License→Binding/Receipt，不接受客户输入epoch作为真源。

原Store writer的test-only connect包装器在同事务先精确UPDATE epoch+1（必须rowcount1），再调用未改动的原revoke_evidence_bundle，原撤销事件/Receipt和epoch一起commit，回滚一起回滚。writer只持epoch，不倒取Installation/Registry，无反序。原源修订append-only不改。

b70两个真实RED作为前测；新增候选后：撤销先在evaluator早快照等待Installation时完成epoch及撤销commit，evaluator FOR SHARE见新tuple应40001，Receipt0/version2；评测先FOR SHARE持epoch时writer精确PID等待eval，eval提交后writercommit，后续新key42501/0。保持原同key/异hash/错tenant/无SELECT等门。范围不能宣称所有多来源写者已覆盖；正式化前需统一写者/DB强制fence及初始化/幂等重放、迁移/恢复锁序合同。

先两个专项真实PG，再默认/b69相邻（已有b67/b49/b50非candidate模式未改条件分支，按受影响范围复核）；编译/diff，前后测试库与随机role/表清理。finally先drop受限函数/policy/role再drop epoch表；异常仍由conftest drop整库。无UI变化浏览器不适用。不启服务/模型/Host/Provider，不写135/读商城源/重放旧Run/碰230L0/push。

原writer实际SET LOCAL ROLE aos_runtime，首跑epoch无policy而0行；补仅test-only表tenant策略与SELECT/UPDATE(epoch)，保留失败。正式epoch写者身份与DB强制门未设计完成，不升级生产权。
