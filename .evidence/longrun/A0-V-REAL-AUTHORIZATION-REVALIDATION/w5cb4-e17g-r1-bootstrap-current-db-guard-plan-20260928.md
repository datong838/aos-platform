# W5CB4 E17-g｜历史 R1 bootstrap 当前库保护计划（2026-09-28）

## 上位与现状

- 231-3/231-9 要求当前配置按正式 Owner/批准和产品入口更新；E17-f 发现 `scripts/aip/bootstrap_r1_runtime_authority.py` 的 `--apply-prerequisites` 直接调用 Budget Store 发布历史金额的 active 预算，`--apply-runtime` 也涉及 Provider/Eval 等写动作。历史 R1 单标注仅 R1 实现、不授权当前 A1 运行。
- 目前当前权威库是 `aos_current_preview_20260927@a0v_109`；R1 脚本不是当前 BG-00 生产者。脚本默认 dry-run 不能因新增守卫连接数据库。当前库继续只读。

## 文件级实施

1. `services/aos-api/tests/aip/test_bootstrap_r1_runtime_authority.py`：RED：模拟只读 DB 身份为当前库，直接调用 `apply_prerequisites()` 与 `apply_runtime()` 均须在任何真实副作用前抛明确 `R1_BOOTSTRAP_DATABASE_BLOCKED`；dry-run 仍不连接；模拟旧 `aos_meta_head` 可经过守卫进入替身后续函数。负例不得触碰真实数据库或 Provider。
2. `scripts/aip/bootstrap_r1_runtime_authority.py`：新增最小只读目标库守卫，用 `connect_read_only(SCOPE)` 读 `current_database()`；只允许历史 `aos_meta_head`，其他任何库（含当前库、未知 clone）失败封闭。在两个写函数的第一步调用守卫，覆盖 CLI 和直接 import；`--verify-runtime` 与默认 dry-run 保留原行为。绝不从 R1 纸面批准推导当前授权。
3. verification：RED/GREEN、脚本相关测试、静态复核；不运行脚本真实 `--apply-*`，不写当前库。m1 精确提交，外部上下文和 D-waves 更新。

## 风险

- 这只堵历史 bootstrap 的两个写函数；其他脚本和直接 Store 写仍由各自入口控制，正式预算 Store 仍需独立批准权威闭环。
