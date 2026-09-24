# W5c4i 自然触发与治理窗口只读验证（2026-09-24）

方案 `d42cfb93`；`scripts/a0v_w5c4i_natural_timing.py` 只读检验正式定义 rev1/hash、当前预算、12 个已保存控制窗口，使用实际 dispatch 同一 `cron_matches` 和 `Asia/Shanghai` 时区逐分钟计算未来 48 小时首次 slot。未配置/启用/手工 Run/读源行。

- 08:11:37 UTC 当前定义仍 disabled；cron `0 4 * * *` 的首次匹配是 **2026-09-24 20:00 UTC = 2026-09-25 04:00 Asia/Shanghai**，不是旧 W5 注释宣称的 04:00 UTC。正式 dispatch 源码按定义 `timezone` 将 UTC slot 转本地后匹配。
- 12 个控制窗口共同有效区间为 2026-09-24 07:50:47–19:50:47 UTC；首次 slot 晚于控制终点 9 分 13 秒，`controlCoversDue=false`。治理预算当前 rev13 有效至 2026-09-25 02:52:33 UTC，覆盖该 slot，但不足以弥补控制过期。故 `enableAllowedByTiming=false`。
- 容器环境 `aos-extension` 当前运行，配置 `cpu: 2`、`memory: 3` GiB。历史 W4 每分钟 cron 首 tick 同时派发 12 条，在同规格 Host 出现租约续订饥饿并 SAFE_BLOCKED（见 `scripts/a0v_w5_definition_rebuild.py` 的事故注释）。这是负载风险证据，不等于本轮已做压力验收。单纯改成更早的 cron 仍会一次派发 12 条，不能证明可完成。

结论：保持新定义 disabled、12 schedule off。下一波方案需要处理两件独立约束：**真实触发点的控制续期**与**12 路同刻负载的有界执行/容量证明**；在两者成立前不 enable，不把配置成功误报为自然执行成功。
