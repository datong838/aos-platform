# W5c7r Installation 锁与时间窗重验审计

专用 18432 PG 的原始 2-member saved input 消费事务 callback 内，第二会话对 exact `bundle_installation` 行只读 `FOR UPDATE NOWAIT` 得 `55P03 LockNotAvailable`；原事务提交后可取锁，零业务行更新。这与 `PipelineSourceSelectionOwner._run_current` 的 installation `FOR UPDATE` 及 RuntimeControl append 经 selection current 入口一致，说明该安装行锁覆盖原 callback。另一独立测试在 callback 后仅测试侧将 `PipelineSnapshotGroupOwner._now` 回答切到原 `expires_at`，后置 GroupOwner `_validate` 拒绝，无新 source call；这是重新调用时间窗守卫的模拟证据，不是实际 DB 时钟自然经过。

新 2 项、联合 W5c7o/p/q/原 InputOwner/SourceClaim Owner 40 项通过。结合 W5c7q 的 Schedule/Run 锁、W5c7p 的 ClaimLoop 身份/历史不可变，可收窄同一 `_load` 重复读性能问题；但仍缺全部派生配置/预算/发布依赖的同事务等价、completed/saved recovery 和错误码证明。尤其不同 `_load` 与 callback 前后必须复核当前与时间窗，不能缓存。**不授权生产优化，也不授权真实 closure。**
