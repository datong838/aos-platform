# W5c4c 第三继任者 12 控制链当前性预检方案（2026-09-24）

## 基线与契约

W5c4a `4d309bd6` 旧 DR 定义正式 retired、12 current member 已释放；W5c4b `2f2f0718` 8080 已由 launchd 唯一受管进程重载。第三继任者九路/Runtime 已恢复，但其 selection/control/binding 仍 0/0/0。产品连续性文件 `2026-09-12-电商运行连续性待办.md` 要求 SourceSelection 绑定当前 SourceConfig/能力/来源范围，不允许从 HTTP 输入任意 SQL/表名、不能默认全店；技术合同 `PipelineSourceSelectionDraft` 限只读、同租户/安装/代际/配置/图/源引用、窗口不超过 24h，正式 Owner 要再核当前四来源/预算。旧 W5 控制脚本仅作构建模板，不可执行旧 key 或读商城源行。

## 本波只读/回滚演练

1. 核 W5c3x/W5c4a/W5c4b 基线、Host PID17302/三 held、12 schedule off、零在途/canary、业务计数不变，当前 Budget rev13/Policy rev13/Price/Model/Route rev12 仍有效。
2. 仅从旧 DS `pipeline_source_selection_revision` 的**受控配置元数据**、当前图 revision/hash、当前 SourceConfiguration ref 和第三继任者配置 ref 构造 12 个候选 draft；不读 Mall 表、Snapshot/Run payload、源返回行。新窗口短且有界，配置/图/来源范围不可扩大。
3. 候选在隔离回滚事务内调用正式 Selection Owner 预检，事务末强制 rollback；保存私有 0600 的 draft 摘要/引用与逐条结果，不生成正式 selection/control/binding。任一当前性门禁失败，不进入写入波。
4. verification 与 m1 commit；下一波才逐条、逐阶段使用新唯一 key 建 12 selection→control→binding，每条独立 intent/Receipt/只读对账，未知不重发。定义配置、启用与自然 worker 观察再分波。
