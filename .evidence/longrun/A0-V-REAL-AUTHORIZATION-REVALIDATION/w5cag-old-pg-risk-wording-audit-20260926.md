# W5cag 当前风险 21/22 精确审计

依据：AOS-000730 `incomplete` 34 条；W5c5x/y/z historical verification、W5caf `29f2bf6a`，当前三文件 collect=12+4+8，单次 18432 opt-in 运行 24 passed。历史 skipped 结果留存，不改旧文件。

| 原当前项 | 已过时的片段 | 新当前表述要保留的事实 |
|---|---|---|
| 21 W5c5x | `Single Executor and Object do not propagate lease`；`old ingress PG 12 skipped` | W5c5y 显式 opt-in 同 lease 下传已在隔离测试证明；旧 ingress 12 + integration 4 + Object 8 本次 24 passed。生产未接线、真库未迁、Store 跨独立提交仍未围栏。 |
| 22 W5c5y | `Link/Retirement/Completion do not pass lease`；`old Single/Object PG skipped` | W5c5z 显式 opt-in Completion→Retirement→Link→Object→Single→Ingress 下传在隔离测试证明；旧套件本次已通过。全机 Host/生产启用和 Store effect 排他仍未证。 |

其余 32 项逐字保持；两条不删、`incomplete` 仍 34、`next_gate` 仍外部 Fleet/历史行或正式退休决策。隔离测试和 opt-in 合同不等于真实执行权或原 12 Run 关闭。若 CAS 冲突冻结而不重放。
