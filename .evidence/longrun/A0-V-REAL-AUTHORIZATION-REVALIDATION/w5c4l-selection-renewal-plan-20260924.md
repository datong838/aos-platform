# W5c4l 第三继任者 12 Selection rev2 续期方案（2026-09-24）

W5c4k `f9aed89c` 冻结了 12 份 24 小时、正式干跑通过的草案及每条 rev1 exact previousRef。新 key 前缀 `a0v-w5c4l-selection-pNN-20260924-v1`，不用旧 W5c4d 键。

1. 只读重核 W5c4k 草案仍在有效窗口、Host/三 held、预算、当前 Selection 仍等于冻结 rev1、12 schedule disabled、新 key 均0、零在途/canary/业务漂移。
2. P01→P12 每条先写 0600 intent（草案、previousRef、key、resend=false），再以正式 `approve_selection` 调用一次并立即写 result；任一结果未知停整波，只读按 key/行对账，不补发。
3. 独立审计每条同 selection ID rev2/previousHash 精确、窗口与草案一致，控制/绑定/定义仍旧 rev1、schedule off、业务不变。verification/commit 后进入 Control rev2 波，不在本波 enable 或手工 Run。
