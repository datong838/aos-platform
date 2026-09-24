# W5c4m 第三继任者 Control rev2 续期验证（2026-09-24）

方案 `5b827c44`；执行 `scripts/a0v_w5c4m_control_renewal.py`。P01–P12 新 key、exact previousRef、0600 intent/result 位于仓库外 `../.aos-recovery-20260920/state/q-advisor-baseline/20260924-w5c4m-control-renewal/`。

- 08:21 UTC 预检 `W5C4M_CONTROL_PREFLIGHT_GREEN`：Selection rev2 12/12；当前 Control 各 rev1 与冻结前序 ref 精确，24 小时草案有效、Host PID17302/三 held、attempt0/canary0、业务 claims40/runs53，新 key0。
- P01→P12 各正式 `approve_control` 只调用一次，逐条先 intent 后 result；返回 `W5C4M_CONTROLS_ACCEPTED`、12/12。
- 08:21 UTC 独立审计 `W5C4M_TWELVE_CONTROL_REV2_GREEN`：Control 累计24行，12 条 rev2 的 previousHash/ref/draft/Selection rev2 引用精确；Binding 仍旧12条，12 schedule off，Host/业务计数不变。`py_compile` 通过。

本波无商城源行读取、手工 Run 或 enable。下一波 W5c4n 才迁 Binding 下一 revision；Definition rev1 仍 disabled 且引用旧 Binding，不能自然执行。
