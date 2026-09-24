# W4 当前僵尸组正式收割 verification（2026-09-24）

## 结论

`W4_STALLED_GROUP_CLOSURE_GREEN`：目标组 `06fa5e56-1ea7-5d08-aa6e-780f58df5ca7` 的 12 条停滞 run 经正式 `a0v_091` 收割服务结算为 failed 终态；stalled=0、closed=12、唯一 receipt=1、`dev-org/dev-project` canary closure=0。既有 source claim/ingress command 保留，没有读取商城源数据、手工 dispatch 或启用 definition。

## 方案与执行记录

- 方案：`w4-stalled-group-closure-plan-20260924.md`（m1 `291cb972`，过期控制链停止条件由 `d0bd66e2` 补充）。
- 执行前主库重新读回：`alembic_version=a0v_091`、数据库时间已过 2026-09-24T02:39:44.133380Z、definition disabled、members=12、stalled=12、closed=0、closure receipt=0、canary receipt=0；8080 health 200，m1 工作树干净。
- `prepare`：`W4_STALLED_GROUP_CLOSURE_PREPARED`，`prepare.json` 0600；请求绑定 group、actor、原 definition rev2/当前 disabled rev3、固定 reason code 与幂等键。独立实时回读在 apply 前仍为 12 stalled、0 receipt、0 canary。
- `apply`：仅一次，`W4_STALLED_GROUP_CLOSED`，`apply.json` 0600；receipt ID `83bd9cc4-2e41-4be0-bd8f-f64e12da331b`，hash `sha256:8b36f4bb61cd04f449685dd62c1c7ed4e15236cf53fd9c98911293b5cf6ab51f`；`businessAccepted=false`、`externalEffects=0`。
- `audit`：`W4_STALLED_GROUP_CLOSURE_GREEN`，`audit.json` 0600；stalled=0、closed=12、receipt=1/hash 精确匹配、canary=0。group claim/input 各 1、members/source claims/ingress commands 各 12，derived commands/dataset receipts 各 0，与收割前一致；未删除既有效应。
- 10:45 后复核：W5 私有目录仍仅 controls/options/w6-recon-frozen 三件；不存在 retire/configure/enable，故不把 W4 GREEN 冒充 W5 GREEN。

## 相邻回归与诚实边界

- 路由修复定向回归 98 passed/7 warnings；调度服务/生命周期相邻测试 20+20+43+7 passed（各自独立测试库）。
- 扩大调度回归的另一次运行前 36 passed，在 `test_claim_ack_and_input_ack_loss_recover_original_group_once` 的数据库游标持续等待，约 5 分钟后中断；该组**不计全绿**，需单独诊断。另一次测试命令因文件名写错未收集，修正后相关 20 项通过；main-deploy 测试首跑缺 `PYTHONPATH=scripts` 导致 4 失败，按项目脚本路径设置重跑后 7 passed。这些测试环境/等待问题不改写正式 W4 receipt 的审计结果。
- W5 旧 controls 的 12 条 selection 已于 2026-09-23T11:59:16.071907Z 过期；预算 head rev12 已于 2026-09-23T16:17:45.943129Z 失效，现行 `options()` 只读报 `budget policy is not effective`。DS binding 只读满足 `settle_released` 前置形态，但**尚未执行**。因此禁止按旧 W5 `configure/enable`；不能覆盖旧冻结文件或复用旧 key。

## 下一波

先冻结 W5 已过期边界并制定全新 direct-successor 方案：正式合成文本证据与预算/运行策略续期、DS 已释放资源的正式 settlement/新配置/启用、当前 12 条 selection/control/binding 重建及独立 state/key，再到新 definition 的自然 dispatch。每段均须现行权威与独立回读；如超过本日 12:00 调度窗，不手工 `run_definition`，按下一自然窗重新确认授权有效期。P0 鉴权与 OpenAPI 差集仍独立待办，不在 W4 收割中混入。
