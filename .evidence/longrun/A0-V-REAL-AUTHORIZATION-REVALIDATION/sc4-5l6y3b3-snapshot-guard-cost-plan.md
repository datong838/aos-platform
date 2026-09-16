# SC4-5L6Y3b-3 整组校验重复成本方案草案

状态：待Y3b-2最终重放验收后实施，未实现。Y3b-2曾在修复栈深后完整succeeded，但单次全路径733.48秒，不能视为性能合格。不得通过提高递归上限、去掉权限/预算/窗口/成员检查、缓存可复用许可来改善耗时。

## 原因与有限优化方向

SourceGroupClaimOwner本来就在原GroupOwner对完整成员的同步current回调中逐Run调用SourceClaimOwner；每个Run新守卫又重入完整12控制，形成重复的N乘N验证。组输入/关系/清退多层复核会放大这个成本。必须先计数原Owner调用与数据库往返，分清真实源等待、Store工作和权限重复核对。

仅对明确位于原完整组同步回调内、循环内容只做原SourceClaim读取/领取的路径考虑内部“当前组上下文”传递：不是持久化/跨事务许可，不是API字段，不可由调用者提供布尔跳过。原SourceClaimOwner对当前成员仍使用原current控制，定义/head/原Run/完整成员/最新binding/共同窗口检查仍执行；仅避免在同一已持有完整组锁的回调里重新展开整组current调用。上下文必须与同conn/scope/原group/actor/所有exact refs匹配，生命周期不能超出同步回调，返回后不得复用。

优先接缝为PipelineSnapshotGroupClaimOwner._operate中的current(group)内部与PipelineSourceClaimOwner私有操作，不改变公共reserve/read API。SourceGuard在没有合法当前组上下文时仍跑完整原GroupOwner。组input逐parent等其他路径先保持严格原行为，不一次性扩大缓存范围。

第二个独立方向是把12成员binding/current-member/schedule的读与稳定排序行锁做有界批量查询；只合并往返，不省略精确引用/权限或把旧查询当current。此项必须先复核安装→定义→控制→schedule锁顺序，不能引入未授权SQL写。

## 验收与停止条件

新增定量测试：原SourceGroup reserve/read在完整当前回调内的snapshot current调用次数从嵌套N乘N降为有界线性；无上下文的单Run恢复保持完整组检查。错误scope/conn/actor/ref、失效/结束的上下文、回调中控制改变/成员停用、过期、负租户、UNKNOWN不重新读取均须拒绝；没有这些证据不启用优化。

随后完整runtime同一真实PG/Store验收、源调用仍1、12对象+1关系/13StoreReceipt/12终态与再次重放零新增，并记录前后总耗时。若无法证明上下文仍受原同步守卫和当前权限约束，保留严格慢路径，不以速度换许可。新设计细节/具体文件必须在编码前补齐。

## 先行的低风险批量化接缝

优先新增PipelineScheduleControlOwner.read_latest_many：同一角色/tenant校验后，有界1..12 schedule IDs一次读取各自最新不可变binding，并逐项复用decode_binding；不接受任意表/SQL。SourceGuard初次和持锁后均通过此Owner读取，不手写替代权限。

SourceGuard的12个schedule行锁合并为有界SELECT ... ORDER BY id COLLATE "C" FOR UPDATE，保持与Python按ID排序的锁顺序；current-member批量读取后逐项检查definitionId与revision。只合并往返，所有成员的exact refs/当前enabled/ingest/pipeline及最新binding比较保留。计划修改aos_api/pipeline_schedule_control_owner.py、aos_api/pipeline_snapshot_schedule_guard.py，新增对应真实PG测试；先测SQL往返数量，index scans不能当语句数量。

## 受限当前组上下文的实现审查要点

若继续做SourceGroupClaimOwner内部重复展开优化，只能在它的current(group)同步回调内创建有界上下文；该回调仅做原SourceClaim读取/领取与原组ledger写，不执行任意外部消费者。上下文必须绑定连接对象/backend事务、线程、scope、group_id、actor、完整refs/Run集合，并在finally退出时失效；不能让公开reserve/read API接受它。实际每个Run仍走原current控制及组定义/成员guard。来自另一连接/事务/线程、错误ref或回调退出后的上下文一律拒绝。所有其他路径保留完整组重验。证明不了这些不变量就只保留安全批量化，不实施上下文路径。
