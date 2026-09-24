# W5c4k 24 小时控制续期草案预检方案（2026-09-24）

W5c4j `683a8b72` 已确定不改运行代码，先用正式 Owner 追加精确 revision 续期。当前新定义 rev1 disabled/12 members、12 schedule off；旧 selection/control rev1 在 19:50:47 UTC 到期，下次自然 slot 20:00 UTC。W5c4k **只生成新草案并干跑**，不提交任何 Selection/Control/Binding/Definition 写入。

1. 只读核 W5c4h/i 状态、Host PID/三 held、九路、预算 rev13 和 canary/业务计数；12 current selection/control/binding 的 exact ref/hash、原 source config/graph/installation config 不变，零在途。
2. 对 P01–P12 从当前 rev1 draft 复制不可变源/映射/graph/安装身份，仅把窗口设为数据库当前 UTC 起至 +24 小时；每项经正式 `PipelineSourceSelectionOwner._guarded(snapshot=True)` 在 rollback 事务中验证，不接触商城源行。记录 current Selection rev1 ref 作为下一波前序。
3. 私有 0600 保存完整草案与前序 ref；Git verification 只写时窗/计数/hash 摘要。若任一草案拒绝或当前权威漂移，验证记录失败并冻结；不先写部分 Selection。
