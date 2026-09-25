# W5c7r Installation 锁与时间窗重验方案（2026-09-25）

## 上位和已证范围

231/231-5 要求当前安装/配置/预算/运行代次与时间窗持续有效。W5c7q 仅证明 Schedule/Run 行锁覆盖 callback；W5c7o/p 仅证明原 fail-closed/ClaimLoop/历史行。`PipelineSourceSelectionOwner._run_current` 对 `bundle_installation` exact 行 `FOR UPDATE`；`PipelineSnapshotGroupOwner._validate` 使用 DB `_now(conn)` 重验共同时间窗。尚不能跳过 claim Owner 的重复 current 验证。

## 文件级九步

1. 复习 231/231-5、W5c7q、SourceSelection/RuntimeControl/GroupOwner、原隔离 PG fixtures。
2. 本方案先提交；仅新增 `services/aos-api/tests/extension_runtime/test_a0v_w5c7r_installation_lock_and_window_pg.py` 与审计/verification，不改生产/迁移/真实 DB。
3. 原 2-member 保存组消费事务 callback 内，第二专用 PG 会话对 exact `bundle_installation` 行 `FOR UPDATE NOWAIT` 应 `55P03`；提交后可取锁。只读锁请求，不更新业务行。
4. 在另一独立用例中，测试侧仅在 callback 后让 GroupOwner `_now` 返回原 group.expires_at，必须由后置原 `_validate` 拒绝；记录这是**模拟时间越界调用合同**，不冒充真实 DB 时钟经过。callback 前/后仍保留原 `_load`。
5. 运行新专项及 W5c7o/p/q/原 InputOwner/SourceClaim Owner 专用 PG 回归与短累计；临时 schema/库 0 后停 PG。旧长例不重跑。
6. 浏览器只读 rev4 disabled，不保存/运行/冲刷队列。
7. 复审：安装锁与时间重验仍不覆盖 completed/saved recovery、全部当前控制派生依赖、异常语义；无完整等价证明不优化生产。
8. verification 提交后 CAS 更新 docs/AOS 上下文与 Prime 独立长记忆并读回。
9. 下一波 W5c7s：方案先行，专门审 completed/saved recovery、异常语义和同事务候选切片的综合可行性；不触真实 closure。

旧真实 attempt 不重发、不手工 `run_definition`；商城源行不读、230 L0 挂起、dev-org 零 canary、m1 单写不 push。
