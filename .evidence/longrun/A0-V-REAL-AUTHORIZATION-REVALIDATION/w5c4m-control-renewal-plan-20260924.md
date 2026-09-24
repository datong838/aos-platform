# W5c4m 第三继任者 12 Control rev2 续期方案（2026-09-24）

W5c4l `371531d1` 的 12 Selection rev2 当前、24 小时窗口覆盖 20:00 UTC slot；12 Control 仍 rev1，旧 definition disabled、schedule off。新 key 前缀 `a0v-w5c4m-control-pNN-20260924-v1`。

1. 只读核 Host/三 held、预算、业务/canary/attempt、Selection rev2 exact、Control rev1 exact 与新 key0；按冻结草案加 rev2 Selection ref 构造正式 `PipelineRuntimeControlDraft`，窗口/映射/安装配置不得变。
2. P01→P12 各先写 0600 intent（draft、previousControlRef、key、resend=false），调用原 `approve_control` 一次后立刻保存新 ref；任何未知结果停整波并只读对账，不重发。
3. 独立审计 12 Control rev2 与 rev1 同 ID、previousHash 精确、引用 Selection rev2；Binding/Definition 仍旧且 schedule off、业务不变。verification/commit 后才进入 Binding 续期波。
