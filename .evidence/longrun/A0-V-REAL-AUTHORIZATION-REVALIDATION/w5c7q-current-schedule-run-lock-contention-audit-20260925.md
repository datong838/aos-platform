# W5c7q Schedule/Run 锁跨会话对抗审计

专用 18432 PG 原始 2-member saved input 在 `PipelineSnapshotGroupInputOwner.run_current` 的同一消费事务 callback 内，第二管理员会话对 exact `meta_schedule` 和 `meta_schedule_run` 行分别发只读 `SELECT ... FOR UPDATE NOWAIT`，两者均 `55P03 LockNotAvailable`；callback 返回且外层事务提交后，第二会话对两行的 NOWAIT 锁都成功，未更改任何行。原 source-call 次数仍为 1，原组 input 在 callback 后保持 current。新专项 1 passed，联合 W5c7o/p/原 InputOwner/SourceClaim Owner 38 passed。

该结果与 `guard_snapshot_schedule_run` 的 Schedule `FOR UPDATE`、`IngressJournal.verify_schedule_binding` 的 Run `FOR SHARE` 一致，证明这两类原行锁覆盖同步 callback。它**不证明**安装/控制最新 revision 的锁及并发可见性，也未覆盖数据库时间窗、completed/saved recovery 与错误码等价；因此不能据此移除 `_bound_parent` 内的第二次 claim Owner 当前读。下一波精确查安装/控制 revision 并发与 DB 时钟，生产/真实 closure 保持不变。
