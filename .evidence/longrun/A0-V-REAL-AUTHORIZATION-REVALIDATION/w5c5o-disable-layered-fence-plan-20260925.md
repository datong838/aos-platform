# W5c5o RuntimeDisable 分层 opt-in 事务围栏方案（2026-09-25）

上位 W5c5h–W5c5n；真实库 `a0v_092`，Host lease/worker guard 均未迁移或启用。RuntimeDisableConsumer 外层 claim/current/finish 通过 `consumer_connection`；RuntimeDisableExecutor 内层另开两次事务先 begin fence 后 finish_disable。仅外层 guard 无法保护真正 disable 状态推进。

## 文件级九步

1. 复习 `disable_consumer.py`、`disable_executor.py`、`disable_commit.py` 两阶段顺序，旧测试和 `a0v_094` guard；列出未纳入的 external dependent/drain 边界。
2. 本方案；仅 `disable_consumer.py` 与 `disable_executor.py` 增可选同 scope `OptInHostLease`，外层所有写事务及内层两事务各自先 guard；新增 `test_a0v_w5c5o_disable_layered_fence_pg.py` 与 verification。默认不传租约完全旧行为；真实 DB/Host/其他 worker 不改。
3. 显式 opt-in 时，不得出现 Consumer 已 guard 但 Executor 未 guard：同一 lease 构造传递；两个 executor transaction 各自检查 token/epoch，再执行 stale settlement、begin/finish。失权/过期拒绝并回滚，不因未知结果手工重发。
4. 隔离 PG 覆盖默认路径、未 acquire/错 epoch/过期拒绝、外层到内层 lease 对象一致；尽可能用真实 DB 函数验证 begin/finish 前门，不能把空队列测试写成 disable 业务完成。
5. W5c3–W5c5o、Host/定义/disable 累计分组回归，记录环境变量顺序债；隔离 PG 停用。
6. 浏览器只读核 A0-V rev4 disabled；不保存/运行/冲刷队列。
7. 本波不覆盖 dependent 外部 effect 的原子性，也不覆盖 ConfigurationStage/PreparedJob/三业务 worker 或全机拓扑；真实 Host/库不启用，旧组关闭严格 24h 与 Owner 独立门不变。
8. verification 提交后 CAS 更新 docs/AOS 项目开发上下文与 Prime 独立受管记忆并读回。
9. 下一波 W5c5p：ConfigurationStage 与相邻 pending/recovery 消费者继续逐事务围栏和故障注入，之后复审所有剩余写路径。

m1 单写不 push；旧 attempt 不重发；商城源行不读；230 L0 挂起；dev-org 零 canary。
