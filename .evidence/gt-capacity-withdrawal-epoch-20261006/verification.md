# 撤回epoch实现检查点（完整Task未收口）

原两旧SER Source/allocation RED已转GREEN；reader-first两路径用pg_blocking_pids实际证明writer等待原native reader，reader.commit后writer完成。集成最终9 passed/23.54s（结构补强之前）；补强后结构/privilege/trigger/FK漂移与原normal withdraw+formal boundary63 passed/89.67s；Source/Evidence/原capacity与Source审查入口102 passed/151.68s。

保留中间失败：首累计107pass/7fail，七项均旧a150固定版本断言（未运行到trigger）；更新为本轮明确a151后旧trigger测试实际通过。首集成6pass/1fail为Source审查抛底层42501，已转换原业务拒绝类型并复验。启动路径错误未运行目标测试，已修正；无未知效果重发。

方案/代码复审：独立owner/table+三函数，严格列/约束/RLS/函数体hash/owner/ACL/extra权限/触发器/FK先后校验；仅明确两reader角色EXECUTE。原Source guard完整原锁链返回后按两个proposal id排序取epoch SHARE。withdrawal AFTER立即FK之后bump避免epoch→proposal逆序；40001/42501均拒绝并要求调用者回滚。普通Action和normal withdrawal保持，原Evidence owner边界未放宽。

代码涉及新151迁移、新fence与PG测试（独立epoch Task）；Source action/formal private审计与版本兼容测试（原formalBoundary Task已同Owner续租）；Source并发集成测试（原Source Task已同Owner续租）。三Task不重复写者/不夺Lease，不改变他人文件。

仍待：有既存撤回数据的150→151历史backfill实际迁移演练，真实恢复副本151全量验证、方案中的进一步损坏/rollback/migration边界审计；完整epoch Task仍ACTIVE，不Delivery。原Source/formalBoundary完整正式签发与publication退出未完成。publication未来152范围须独立对账；原150恢复证据保留但不证明151。当前源库仍142，未修改/迁移/重启；Host/worker/Provider未开，不push。

## 非空历史迁移函数补验
最终文件13passed/7warnings22.40s，包含原11项及两个非空历史用例。一次隔离事务恢复151相关对象创建前结构，保留非空原proposal/withdrawal快照，调用真实migration.upgrade，逐proposal比较epoch与原撤回计数并证明原行不变；原已撤回锁42501拒绝。延迟FK时真实迁移拒绝，回滚savepoint后无新表、原行不变，再执行正常迁移成功。整个测试事务rollback后原151表和版本恢复。
边界：不是完整Alembic150→151版本事务演练，不是完整历史恢复副本验收；当前恢复副本仍150且该两表为空，源库未迁移。最初两次失败均测试驱动选择错误，未运行迁移，不称业务RED；历史backfill-r2为中间1pass，rollback为补锁前13pass，complete为最终13pass。方案与代码一致，DDL全部仅aos_test_隔离库事务，未改生产代码；完整Task保持ACTIVE。

## 2026-10-06 12:53 完整版本事务与中途失败验收
本节覆盖前述“未验完整Alembic版本事务”；源库现状以AOS-001370维护151事实为准，前述源142/恢复150是历史时间点，不触发重放。

仅扩展原PG测试及本证据目录，生产迁移/原env/fence未改。原env的supplied connection入口运行真实command.upgrade、revision和version更新：隔离非空历史结构150→151成功，逐proposal epoch精确等于历史撤回计数、原proposal/withdrawal全文快照不变；已撤回reader仍42501拒绝。延迟FK前置拒绝和同名函数中途DuplicateFunction拒绝，均savepoint回滚；中途失败发生在建表/回填/owner/RLS已执行后。版本仍150、新表/三函数/两trigger均不存在、完整public schema ACL精确等于之前、原行快照不变；正常再升级151，外层rollback恢复初始151。

首次版本事务专项15passed/7warnings24.31s，相邻84passed/7warnings108.10s。中途失败补强首轮82passed/4failed108.78s：4项均测试错误地把PUBLIC继承的有效USAGE当独立owner直接授权；不是生产RED。改为比较原schema ACL全文后，最终本文件+原Action+formalBoundary **86passed/7warnings112.71s exit0**，日志alembic-adjacent-r2.log。全部只用5433本轮新建aos_test_隔离库，按fixture保留，不清理库/卷。最初启动路径exit127未执行测试，alembic-version-transaction.log保留。

方案/代码复审：真实原入口无替代migration runner；错误异常类型/文本符合PG；savepoint包括故障注入，新DDL和ACL都有恢复断言；原函数用例保留，未篡改生产版本记录或降低迁移downgrade拒绝；scope/Lease同Owner有效且无重叠。diff --check通过。无UI改动，本切片无需新增浏览器操作。本证据是重建非空历史结构的事务验收，不等于完整历史备份恢复、正式Source/Capacity发布或首链。完整epoch Task仍ACTIVE，原恢复副本native全量验收及更多损坏边界待核；不Delivery，不complete Goal。

收尾：代码/证据提交d9244aca，authority经原memoryctl CAS推进AOS-001371；原sync适配器同步AOS/Prime，实际回读全部7个强一致投影CURRENT、memory-validate GREEN。此次未获直接Codex记忆更新请求，运行时写入范围明确排除该可选异步adapter，未改全局代码/manifest；Codex旧1370 note显示STALE，不宣称其摄入。Goal实际回读active，Task保持ACTIVE。下一已登记步骤是恢复151原native边界验收与full b90真实生产输入组合；当前权威库不再执行维护。
