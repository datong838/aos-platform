# W5c4d 第三继任者 12 SourceSelection 签发验证（2026-09-24）

方案 `2190c369` 已完成。W5c4c 的 12 条私有 0600 draft 在当前有效窗内，第三继任者 installation/generation/epoch3/configRef 精确，旧 DR 定义 retired、12 schedule off、零业务在途与 canary。原 `PipelineControlServices.approve_selection` 按 P01→P12 各调用**一次**；每条均有独立 0600 intent/result 和新唯一 key `a0v-w5c4d-selection-pNN-20260924-v1`，无重发。

独立数据库逐条读回并解码正式 immutable selection：12 个 pipeline 各唯一 rev1，key/ref/hash/draft 与私有材料精确相同；审计 `W5C4D_TWELVE_SELECTIONS_GREEN`。第三继任者 control/binding 仍 0/0，12 schedule enabled=0，旧定义 retired、九路/Runtime/claim gate 不变，业务 claims40/runs53 不变。Selection 只是已批准的只读控制元数据，不代表源已读取或业务执行；本波未读商城源行、未创建 Run。

下一波以 12 条正式 SelectionRef 逐条签发 RuntimeControl，仍保持 12 schedule off；随后独立波绑定 schedule，再配置/启用新定义。有效窗为预检时起 12 小时，不能默认为永续授权。
