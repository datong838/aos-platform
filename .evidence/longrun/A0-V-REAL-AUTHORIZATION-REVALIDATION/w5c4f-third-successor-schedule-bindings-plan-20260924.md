# W5c4f 第三继任者 12 ScheduleBinding 串行迁移方案（2026-09-24）

W5c4e `5eface42` 已有 12 条当前 RuntimeControl rev1，逐条精确引用第三继任者 Selection；新 schedule binding 仍0，旧 12 个 schedule disabled、最新 binding 指向已卸载 DS，旧 DR definition rev4 retired/current member0。正式 `PipelineScheduleControlOwner.bind` 要求 exact 当前 control、同 pipeline/schedule、最新 previous binding ref，追加同 binding ID 连续 revision；不替换 schedule ID，也不会自动启用。

1. 复核 W5c4e/旧定义/九路/Runtime/Host/三 held、控制窗口仍有效、12 schedule off、零在途/canary、业务计数不变；读取 12 个当前旧 DS binding 的精确 ref/hash/revision，确保它们仍是最新且新安装 binding0。
2. P01→P12 各以新唯一 key，先 0600 intent 固定 pipeline/schedule/controlRef/previousRef，再调用原 `PipelineControlServices.bind_schedule` **一次**，立即保存 ref。任一结果未知，停整波按 key/行只读对账，不重发、不执行余项。
3. 只认 12 个 immutable 新 binding：安装/代际为第三继任者，controlRef 一一对应，ID 继承旧 DS binding、revision 连续+1，12 schedule 仍 disabled/current member0、业务计数不变。verification/commit。
4. 下一波从正式 SnapshotScheduleService.options 只读选定当前 policyRef 与 12 binding，独立配置新的 disabled definition；启用/自然 worker 再分波。不读商城源行、不手工 Run、不 push。
