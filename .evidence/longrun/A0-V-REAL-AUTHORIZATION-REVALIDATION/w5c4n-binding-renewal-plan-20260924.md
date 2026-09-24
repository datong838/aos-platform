# W5c4n 第三继任者 12 Binding 续期方案（2026-09-24）

W5c4m `ff350a17` 的 12 Control rev2 当前且精确指向 Selection rev2。W5c4f 的 12 Binding 仍指向 Control rev1；新定义 rev1 disabled/12 current members。新 key 前缀 `a0v-w5c4n-binding-pNN-20260924-v1`。

1. 只读核 W5c4m、12 最新 Binding exact ref、definition rev1 disabled、12 schedule off、Host/三 held、预算/窗口、零在途/canary、业务不变，新 key0。
2. P01→P12 各先 0600 intent 固定 schedule/control rev2/previousBindingRef/key，再调用正式 `bind_schedule` 一次并立即保存新 ref；未知结果停整波、只读对账，不重发。
3. 独立审计同 binding ID、新 revision 连续+1、previousHash 精确、controlRef=rev2，definition 仍 disabled、schedule off。verification/commit；下一波 disabled definition rev2 配置最新成员，仍不 enable。
