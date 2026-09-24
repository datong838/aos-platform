# W4 当前僵尸组正式收割执行计划（2026-09-24）

## 前提与目标

- 目标仅为 group `06fa5e56-1ea7-5d08-aa6e-780f58df5ca7` 的 12 条已停滞 run，通过 `a0v_091` 正式服务收割为终态；不删除既有效应，不读取商城源数据，不手工 dispatch。
- 继承 `scripts/a0v_w4_stalled_close.py` 内建三阶段约束、D-waves《无人值守交接简报》10:45 验收卡和 W3 同类正式通道；此计划不更改脚本、迁移或目标常量。
- 最早执行时刻为 2026-09-24T02:39:44.133380Z（北京时间 10:39:44），此时间之前只允许只读核查。

## 10:02 CST 当前只读基线

- `m1@36539dc6`，工作树干净；8080 新进程健康 200。
- 当前组：definition `disabled`，members=12、stalled=12、closed=0、closure receipts=0，`dev-org/dev-project` canary receipts=0。
- 既有效应计数：group claim/input 各 1、group members 12、source claims 12、ingress commands 12、derived commands 0、dataset receipts 0。效应非零必须如实保留，不按“空组”处理。
- W5 只读 verify：旧 definition rev3 `disabled`，新 definition 不存在；W5 私有 controls/options 已冻结，各 12 members，配置 rev1、epoch3。

## 串行步骤与退出条件

1. 到时后重新检查 Git、8080、state 目录与当前组事实；若成员数、状态、receipt/canary 或迁移头漂移，中止，先只读定性。
2. 运行 `services/aos-api/.venv/bin/python scripts/a0v_w4_stalled_close.py prepare`；必须得到 `W4_STALLED_GROUP_CLOSURE_PREPARED`，并冻结 `prepare.json`。脚本会校验 `a0v_091`、24 小时、12 stalled、definition disabled、receipt/canary 0。
3. 独立回读 `prepare.json` 与当前组，确认精确 group、actor、definition ref 与上述事实；不以 stdout 单独放行。
4. 运行同脚本 `apply`；必须得到 `W4_STALLED_GROUP_CLOSED` 且冻结 `apply.json`。若返回未知或文件未落盘，停止，先查正式 receipt 和 run 状态，绝不重发。
5. 运行同脚本 `audit`；必须得到 `W4_STALLED_GROUP_CLOSURE_GREEN`，12/12 terminal、receipt/hash 匹配、canary=0，冻结 `audit.json`。
6. 写独立 verification 文件，核对方案/结果/风险与 `git diff --check`，提交 m1；不 push。下一波才允许 W5 `retire → configure → enable → verify`，逐段回读、遇未知边界停止。

任何一步失败均不跳级、不手动运行 definition、不用新 key 重放。W3 历史组的 GREEN 不能代替本组 W4 证据。
