# W5c4e 第三继任者 12 RuntimeControl 正式签发方案（2026-09-24）

W5c4d `d6f1d39e` 的 12 条 SourceSelection rev1/唯一 key/ref/hash 已逐条正式回读；新 control/binding 0/0，12 schedule off，旧定义 retired。Selection 窗口至 2026-09-24 19:50 UTC 左右，不可视为永续授权。

1. 复核 W5c4d 正式审计、每条 SelectionRef 当前、第三继任者 Runtime/Host/三 held、预算/四来源/源配置/图与 draft 窗口、12 schedule off、零在途/canary，12 新 control key/行均0。
2. P01→P12 每条从原 SelectionDraft 只变更 `schemaVersion` 为 RuntimeControlDraft 并加入当前精确 `sourceSelectionRef`，先单独 0600 intent，再由原 `PipelineControlServices.approve_control` 以新唯一 key/无前任 ref 调用一次，立即保存结果。任何未知边界停整波只读对账，不重发余项。
3. 独立按 immutable control 行解码，验证 12/12 rev1、绑定各自 SelectionRef、draft/key/ref/hash 精确，schedule binding 仍0、12 schedule off、业务计数不变；verification/commit。
4. 下一波才将 12 条 control 绑定现有 schedule ID；定义配置/启用继续后置。不读商城源行、不手工 Run、不 push。
