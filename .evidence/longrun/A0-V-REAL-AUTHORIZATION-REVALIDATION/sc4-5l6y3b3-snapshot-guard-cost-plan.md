# SC4-5L6Y3b-3 整组校验重复成本方案草案

Y3b-3a收口：最终定向21 passed / 19.48秒（/tmp/aos-snapshot-batch-final2.log），整组runtime 7 passed / 723.54秒，git diff --check通过。memory-status为GREEN_WITH_WARNINGS（旧全局投影AOS-000573、异步笔记PENDING_ASYNC），只作辅助健康信息，本波事实以本证据/提交为准，不修改Codex记忆。主库仍061、主服务未重载、真实源调用0。下一波Y3b-3b按独立方案先Red验证调用次数，再实现受限循环上下文。

实施切片Y3b-3a：只做有界批量查询，不实现当前组上下文。新增测试文件services/aos-api/tests/extension_runtime/test_snapshot_guard_batch_pg.py；修改两个Owner/guard文件如后文。read_latest_many保留输入顺序、缺项返回None、拒绝重复/空/超过12项，固定public表名防search_path遮蔽；当前成员同时比较definition revision。测试实际Cursor.execute调用次数，验证最新binding、负租户、缺项、边界和整组guard仅两次binding SELECT。后续是否减少同步重复展开另行审核，不能把本切片当作完整性能解决。

状态：Y3b-2完整重放已通过824.49秒；Y3b-3a批量读取已实现，19项真实PG测试通过18.63秒，完整runtime复验进行中。Y3b-3b同步循环上下文另见sc4-5l6y3b3b-current-group-loop-plan.md，尚未实施。不得通过提高递归上限、去掉权限/预算/窗口/成员检查、缓存可复用许可来改善耗时。

## 原因与有限优化方向

SourceGroupClaimOwner本来就在原GroupOwner对完整成员的同步current回调中逐Run调用SourceClaimOwner；每个Run新守卫又重入完整12控制，形成重复的N乘N验证。组输入/关系/清退多层复核会放大这个成本。必须先计数原Owner调用与数据库往返，分清真实源等待、Store工作和权限重复核对。

仅对明确位于原完整组同步回调内、循环内容只做原SourceClaim读取/领取的路径考虑内部“当前组上下文”传递：不是持久化/跨事务许可，不是API字段，不可由调用者提供布尔跳过。原SourceClaimOwner对当前成员仍使用原current控制，定义/head/原Run/完整成员/最新binding/共同窗口检查仍执行；仅避免在同一已持有完整组锁的回调里重新展开整组current调用。上下文必须与同conn/scope/原group/actor/所有exact refs匹配，生命周期不能超出同步回调，返回后不得复用。

优先接缝为PipelineSnapshotGroupClaimOwner._operate中的current(group)内部与PipelineSourceClaimOwner私有操作，不改变公共reserve/read API。SourceGuard在没有合法当前组上下文时仍跑完整原GroupOwner。组input逐parent等其他路径先保持严格原行为，不一次性扩大缓存范围。

第二个独立方向是把12成员binding/current-member/schedule的读与稳定排序行锁做有界批量查询；只合并往返，不省略精确引用/权限或把旧查询当current。此项必须先复核安装→定义→控制→schedule锁顺序，不能引入未授权SQL写。

## 验收与停止条件

Y3b-3a完整runtime复验：/tmp/aos-snapshot-batch-runtime.log，7 passed / 723.54秒，含领取/input响应丢失恢复、原完成重放和六个失败边界。业务数量与源调用1不变。前一版仅成功路径824.49秒，本次整模块723.54秒，测试集合和运行时负载并非严格相同，不报告精确性能百分比；已证明查询合并和完整逻辑仍成立，但耗时仍长，需要下一切片。定向真实Cursor测量：一次源claim守卫的binding SELECT由24次降为2次，两个批量查询均重新读取当前绑定，没有跨事务缓存。

新增定量测试：原SourceGroup reserve/read在完整当前回调内的snapshot current调用次数从嵌套N乘N降为有界线性；无上下文的单Run恢复保持完整组检查。错误scope/conn/actor/ref、失效/结束的上下文、回调中控制改变/成员停用、过期、负租户、UNKNOWN不重新读取均须拒绝；没有这些证据不启用优化。

随后完整runtime同一真实PG/Store验收、源调用仍1、12对象+1关系/13StoreReceipt/12终态与再次重放零新增，并记录前后总耗时。若无法证明上下文仍受原同步守卫和当前权限约束，保留严格慢路径，不以速度换许可。新设计细节/具体文件必须在编码前补齐。

## 先行的低风险批量化接缝

补充负例初次失败原因：原配置Owner已将外键约束设为IMMEDIATE，故测试制造旧member revision时先被数据库拒绝，尚未进入应用守卫（8 passed/1 failed，10.10秒）。测试改为仅在必回滚的隔离事务内将两个原DEFERRABLE约束设为DEFERRED，验证提交前应用守卫也拒绝；不禁用约束、不改生产实现。临时同名binding表遮蔽负例已通过。

优先新增PipelineScheduleControlOwner.read_latest_many：同一角色/tenant校验后，有界1..12 schedule IDs一次读取各自最新不可变binding，并逐项复用decode_binding；不接受任意表/SQL。SourceGuard初次和持锁后均通过此Owner读取，不手写替代权限。

SourceGuard的12个schedule行锁合并为有界SELECT ... ORDER BY id COLLATE "C" FOR UPDATE，保持与Python按ID排序的锁顺序；current-member批量读取后逐项检查definitionId与revision。只合并往返，所有成员的exact refs/当前enabled/ingest/pipeline及最新binding比较保留。计划修改aos_api/pipeline_schedule_control_owner.py、aos_api/pipeline_snapshot_schedule_guard.py，新增对应真实PG测试；先测SQL往返数量，index scans不能当语句数量。

## 受限当前组上下文的实现审查要点

代码复核补充：PipelineSnapshotGroupClaimOwner._operate.current只执行原SourceClaim元数据读/领取和组ledger写，不执行源reader或任意业务消费者；它是未来上下文的唯一签发接缝。PipelineSourceSelectionOwner已在执行前锁installation，并经run_guarded检查当前runtime/config/权限，回调结束再次检查窗口；原GroupOwner对全部控制在消费前后复核。未来优化只可以省去这一特定循环中嵌套的GroupOwner展开；每个成员自身SourceClaim的run_current、预算/原Run检查、exact定义与成员核对仍保留。事务内修改其他成员必须被外层postcheck拒绝并整体回滚，不能把事务内暂存成功误报为提交成功。SourceGroup的reserve已有savepoint，read调用仍由外层事务负责回滚；不得新增外部副作用。

尚未实施上下文优化：需新增专用私有模块，在同步回调内用ContextVar限定作用域，并把连接对象、backend pid、当前事务id、线程、scope、group_id、actor、完整ref/Run集合与CurrentSnapshotGroup绑定。内部检查只返回当前group给守卫重验共同窗口，不导出可复用许可；finally清除并失效。无上下文走完整原路径；有上下文却身份不符必须拒绝，不能静默降级。必须覆盖复制context到另一线程/连接、结束后复用、嵌套上下文、窗口过期、回调内其他控制supersede/成员停用整体回滚。若无法满足，维持严格路径。

若继续做SourceGroupClaimOwner内部重复展开优化，只能在它的current(group)同步回调内创建有界上下文；该回调仅做原SourceClaim读取/领取与原组ledger写，不执行任意外部消费者。上下文必须绑定连接对象/backend事务、线程、scope、group_id、actor、完整refs/Run集合，并在finally退出时失效；不能让公开reserve/read API接受它。实际每个Run仍走原current控制及组定义/成员guard。来自另一连接/事务/线程、错误ref或回调退出后的上下文一律拒绝。所有其他路径保留完整组重验。证明不了这些不变量就只保留安全批量化，不实施上下文路径。
