# W5c4e 第三继任者 12 RuntimeControl 签发验证（2026-09-24）

方案 `8114599f` 完成。W5c4d 的 12 条 SelectionRef 逐项仍当前、draft 窗口有效，第三继任者 Runtime/Host/三资源与调度静默。P01→P12 各由原 `PipelineControlServices.approve_control` 单次签发；每条新唯一 key `a0v-w5c4e-control-pNN-20260924-v1`、独立 0600 intent/result，control draft 精确引用同 pipeline 的新 SourceSelectionRef，无旧 DS ref 复用或重发。

独立解码 12 条 immutable control 行：每 pipeline 唯一 rev1、idempotency key/ref/hash/draft 与私有材料一致，`sourceSelectionRef` 一一对应；`W5C4E_TWELVE_CONTROLS_GREEN`。第三继任者 schedule binding 仍0，12 schedule enabled=0，旧 DR definition retired，九路/Runtime/claim gate 和业务 claims40/runs53 未变化。未读商城源行、未创建 Run。

下一波以当前 12 个 control ref 对应绑定 12 个原 schedule ID，expected previous binding 必须精确指向旧 DS 最新 ref；成功后再独立配置新 disabled definition。Selection/Control 有效窗仍受限，定义启用与自然 worker 观察不得跳步。
