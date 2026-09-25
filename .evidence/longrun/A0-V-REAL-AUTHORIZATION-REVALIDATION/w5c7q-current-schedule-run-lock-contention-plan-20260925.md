# W5c7q 当前 Schedule/Run 锁并发对抗方案（2026-09-25）

W5c7n 的 claim 热点、W5c7o/p 的原行为与身份/历史不可变合同均不足以证明同一 `_load` 复用。231/231-5 仍要求当前权限与原运行绑定。源码 `guard_snapshot_schedule_run` 对 group Schedule `FOR UPDATE`，`IngressJournal.verify_schedule_binding` 对 Run `FOR SHARE`；需证实原消费 callback 持锁期间另一会话不能改变其所见状态，仍不自动推断可删第二次 claim Owner 读。

## 文件级九步

1. 复习 231/231-5、W5c7l/o/p、Group/InputOwner、Schedule guard 与 Journal 的锁序；核对专用 18432 PG fixture。
2. 本方案先提交；仅新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c7q_schedule_run_lock_contention_pg.py`、审计与 verification，不改生产/迁移/真实库。
3. 在已保存的原始 2-member 组的同一消费事务 callback 内，另开专用 PG 会话，对 exact Schedule 与 Run 发 `SELECT ... FOR UPDATE NOWAIT`（零数据修改）；预期均 `55P03`，原回调成功后 group 仍 current。
4. 锁保持、callback 前后 `_load` 的次序及 RLS 当前租户绑定须在专项目标中读回；任何未预期可获取锁即作为失败/风险，不以测试改写生产合同。连接用后关闭。
5. 跑专项与 W5c7o/p/原 InputOwner/SourceClaim Owner 专用 PG 回归、短累计；检查临时 schema/库 0，停 PG。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 复审：Schedule/Run 锁只是部分证明，安装/控制最新 revision、数据库时钟、completed/recovery、原异常语义仍需独立证明；未经完整等价证明不优化生产。
8. verification 提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7r：方案先行，补安装/控制 revision 并发可见性及 DB 时钟负例；不触真实 closure。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读，230 L0 挂起，dev-org 零 canary，m1 单写不 push。
