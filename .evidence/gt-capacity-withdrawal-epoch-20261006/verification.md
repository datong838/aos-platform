# 撤回epoch实现检查点（完整Task未收口）

原两旧SER Source/allocation RED已转GREEN；reader-first两路径用pg_blocking_pids实际证明writer等待原native reader，reader.commit后writer完成。集成最终9 passed/23.54s（结构补强之前）；补强后结构/privilege/trigger/FK漂移与原normal withdraw+formal boundary63 passed/89.67s；Source/Evidence/原capacity与Source审查入口102 passed/151.68s。

保留中间失败：首累计107pass/7fail，七项均旧a150固定版本断言（未运行到trigger）；更新为本轮明确a151后旧trigger测试实际通过。首集成6pass/1fail为Source审查抛底层42501，已转换原业务拒绝类型并复验。启动路径错误未运行目标测试，已修正；无未知效果重发。

方案/代码复审：独立owner/table+三函数，严格列/约束/RLS/函数体hash/owner/ACL/extra权限/触发器/FK先后校验；仅明确两reader角色EXECUTE。原Source guard完整原锁链返回后按两个proposal id排序取epoch SHARE。withdrawal AFTER立即FK之后bump避免epoch→proposal逆序；40001/42501均拒绝并要求调用者回滚。普通Action和normal withdrawal保持，原Evidence owner边界未放宽。

代码涉及新151迁移、新fence与PG测试（独立epoch Task）；Source action/formal private审计与版本兼容测试（原formalBoundary Task已同Owner续租）；Source并发集成测试（原Source Task已同Owner续租）。三Task不重复写者/不夺Lease，不改变他人文件。

仍待：有既存撤回数据的150→151历史backfill实际迁移演练，真实恢复副本151全量验证、方案中的进一步损坏/rollback/migration边界审计；完整epoch Task仍ACTIVE，不Delivery。原Source/formalBoundary完整正式签发与publication退出未完成。publication未来152范围须独立对账；原150恢复证据保留但不证明151。当前源库仍142，未修改/迁移/重启；Host/worker/Provider未开，不push。

## 非空历史迁移函数补验
最终文件13passed/7warnings22.40s，包含原11项及两个非空历史用例。一次隔离事务恢复151相关对象创建前结构，保留非空原proposal/withdrawal快照，调用真实migration.upgrade，逐proposal比较epoch与原撤回计数并证明原行不变；原已撤回锁42501拒绝。延迟FK时真实迁移拒绝，回滚savepoint后无新表、原行不变，再执行正常迁移成功。整个测试事务rollback后原151表和版本恢复。
边界：不是完整Alembic150→151版本事务演练，不是完整历史恢复副本验收；当前恢复副本仍150且该两表为空，源库未迁移。最初两次失败均测试驱动选择错误，未运行迁移，不称业务RED；历史backfill-r2为中间1pass，rollback为补锁前13pass，complete为最终13pass。方案与代码一致，DDL全部仅aos_test_隔离库事务，未改生产代码；完整Task保持ACTIVE。
