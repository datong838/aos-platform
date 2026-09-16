# Y3b-3b 原组SourceClaim循环的受限同步上下文

最终补充：原单路SourceClaim隔离024合同19 passed/5.83秒（显式AOS_EXTENSION_PG_TEST=1）；初次未给会话隔离库地址导致默认5433拒绝连接，配置18434测试admin后通过，实际旧schema仍在18432，不涉及主库。git diff --check通过。原组完整性约束修复只延后本组header/member约束并在返回前立即验证，外层ALL IMMEDIATE正例通过。实施与本方案一致：仅原SourceGroup固定元数据循环生效，其他路径保留全检查，没有新源调用/权限令牌/跨事务缓存。

完整runtime最终通过：7 passed / 462.52秒（/tmp/aos-snapshot-context-runtime.log），同模块上一版723.54秒。源调用仍1、12成功Run/12对象/1关系/13 StoreReceipt及其他原回执数不变，完成后原组重放零新增。41项上下文/批量/守卫/native claim验证及4项原input回归通过。这个结果证明本次有界优化有效，不代表真实数据性能或经营首链已完成；主库061/服务未变。下一波转Y3c正式续期恢复，保留性能观察，不扩大同步上下文范围。

状态：实施前设计，待Y3b-3a批量查询完整回归完成；不是通用缓存或新增授权。

## 边界与文件

仅PipelineSnapshotGroupClaimOwner._operate.current内的原SourceClaim循环可设置上下文。该回调只读写受事务控制的claim元数据，不调用源、Store或外部消费者。新增aos_api/pipeline_snapshot_claim_context.py（私有辅助）、tests/extension_runtime/test_snapshot_claim_context_pg.py；修改pipeline_snapshot_group_claim_owner.py、pipeline_source_claim_owner.py、pipeline_snapshot_schedule_guard.py。不得将上下文加入公共API或持久化。

guard_snapshot_schedule_group成功核验v2原schedule回执、group_id、actor及完整ref/Run集合后，可返回该只读事实给原SourceGroupOwner；旧单路/legacy无此事实则维持原路径。返回事实不是许可，只有在随后原GroupOwner的完整current同步回调内才创建上下文。

## 生效条件

上下文持有连接对象、backend pid、当前已分配事务id、线程id、scope、actor、原group_id、全部exact ref/Run和已验证CurrentSnapshotGroup。使用ContextVar限定当前同步调用链，finally还原外层context且将本实例标记失效；不支持await/deferred。嵌套只能独立核验，不能借父上下文免检新组。

SourceClaim._operate入口在获取任何控制锁前，若检测上下文则核对conn/thread/transaction/scope/actor/ref/Run，避免错误连接拿安装锁死等。每成员仍执行原controls.run_current、SourceClaim预算/历史/Run校验及guard的exact定义、最新bindings与当前成员检查。只有当guard从自身原schedule回执读出的完整ref/Run/group均与当前上下文一致时，才用原GroupOwner._validate在同事务内复核共同窗口，再执行原schedule/member校验，省去内层再次展开十二个run_current_snapshot。无context仍完整展开；有context不匹配必须拒绝。

外层GroupOwner已持有安装/当前配置/控制所需锁，并在循环前后对全部成员核验；并发变更被锁阻挡，同事务其他控制supersede/停用或窗口到期必须导致外层失败和整个reserve savepoint回滚。不能吞异常或把循环中临时claim当已提交。原有read调用不新增副作用，失败由调用者事务负责回滚。

## 验证与退出条件

当前定向结果：先修复IMMEDIATE接缝后，次数Red实测312 != 24（6.11秒）。实现后正向2 passed/5.89秒；完整上下文/批量/定义守卫/native组claim 41 passed/36.22秒；原native input四项通过19.00秒。跨连接/租户/actor/ref/Run/group/线程、嵌套、退出后复制context及真实提交后换事务全部拒绝；第12成员前停用/控制supersede/窗口到期/抛异常均整体回滚并清理上下文，正常再次reserve可成功。中间首次实现误读groupId顶层字段已改为原request.groupId；换事务独立连接返回tuple时沿用原_values兼容读取，最终测试覆盖。完整runtime恢复与重放正在复验，尚不计通过。

首轮Red先暴露原SourceGroupOwner在外层ALL IMMEDIATE时写组header被045完整成员约束提前拒绝（5.75秒），尚未进入次数断言。先在该Owner创建组header前仅设置schema限定的complete_snapshot_group约束DEFERRED，全部members插入后IMMEDIATE；保留数据库完整性且在返回前验证。新增显式ALL IMMEDIATE正例，之后重跑原计数Red确认312次。此修复不修改迁移/约束定义，也不把全事务其他约束延后。

先用真实十二定义组计数重现原SourceGroup reserve约312次snapshot current展开；新路径必须只有外层前后24次，原单个SourceClaim无上下文依旧24次。验证原reserve→read→completed、幂等零新增、源调用0；错误conn/scope/actor/ref/group、已退出上下文、复制到其他线程、事务变更必须拒绝。回调内改另一控制/停用另一成员须整体回滚；窗口过期不产生部分claim；异常必须清理context使后续正常调用走完整守卫。

随后19项批量/守卫回归、原native claims/input、完整runtime原组恢复与重放，比较实际耗时和原业务Receipt数量。上下文只用于这一个循环，其他Input/Projection/Store调用保持原始全检查。若证明不足，不扩大优化范围，记录限制继续严格实现。
