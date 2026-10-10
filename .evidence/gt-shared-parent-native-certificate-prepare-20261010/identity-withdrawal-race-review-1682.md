# 原身份撤回双向竞争复审

Rules：231、既有Task9/10/Task3 scoped Lease、m1单施工、ownedlab随机新库、原件闭合权限；无产品代码更改。本波文件位于本Task native-r21/native-r22、两个独立只读核对脚本/结果、计划，以及Task3两个对应实验前缀。

R21读者先持锁：完整原prepare/Python reader四证书正向后，数据库pg_blocking_pids实际确认撤回写者被风险读者阻塞。风险实际COMMIT被原deferred门拒绝并ABORT，写者随后合法immutable withdrawal COMMIT；新私有原件身份读取拒绝已撤回头。完整节点1PASS/111.13秒。

R22写者先持锁：原风险首SERIAL快照已建立，原immutable withdrawal INSERT持身份更新锁；实际pg_blocking_pids确认风险读者被撤回写者阻塞后写者COMMIT。原SQL入口严格40001拒绝旧快照，保存点回滚、caller xid/pid不变且外层live，Manifest缺失；风险最终COMMIT仍原门拒绝并ABORT。完整节点1PASS/84.09秒。不能把40001当成新的安全快照成功或自动重发许可。

两个独立READ ONLY核对确认risk ABORTED，实验Root/合法旧元数据身份登记/withdrawal均COMMITTED；四风险表和当前v3 Manifest/binding零，六类合法legacy记录各1原件hash吻合保留，globalhead2/2/false；四SQL函数精确body/Owner/固定search_path/PUBLIC无权限，原C verifier仍仅两个原Owner，runtime无私表权限；十二产品/test哈希未变。337纯专项先前结果同hash，不重复计数；无浏览器产品变化，浏览器不适用本隔离数据库竞争波。

复审实现：线程捕获精确隔离DB连接参数，限时监控实际锁关系、仅commit返回后写terminal；先记录intent，join确认结束，独立事务状态回读。线程是隔离协议actor而非第二代码施工写者。保存点异常断言在包装外，避免被固定错误包装吞掉。没有关闭trigger、绕过Owner、模拟时钟或延长原证书/审批。

范围与风险：旧v1登记申请字段是合成metadata，Root bootstrap谱系未验证；两case最后新读取仅私有legacy原件身份当前性，不宣称再次完整新v3风险（该终止另见R19）。这仅证明原件身份锁与撤回必要门，无合法finaljoint、WAL ACK期限、正式安装/经营授权、自然首链或发布验收。Task9/10仍ACTIVE无Delivery。未知效果不重发，数据库/不可变history保留。

下一已登记候选：①完整joint finalizer原件合同与deferred队列审计；授权设计/隔离实现，依赖原预算事实桥、Source最终期限、Root正式谱系与原caller同txn Intent。②正式IssuerRoot信任谱系验收；依赖正式身份/安装签发来源，实验bootstrap不授信。先选①开展具体写入顺序与结束队列调查，不能通过无条件拒绝门改成常真放行。
