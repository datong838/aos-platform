# Y5f4-P L 真实商品自然 Cron 入口验证

日期：2026-09-17

代码基线：`f5f81d62`
租户：`org-org/dev-project`；`dev-org/dev-project` 仅作零触发 canary。

## 结论

`L_NATURAL_PRODUCT_CRON_SOURCE_FAILED_CLOSED`。本波没有做绿：系统自身 Cron 在上海时间 2026-09-17 00:00 自然领取唯一运行 `scr-09fc7164153f4d7d`，`trigger=cron`，证明 schedule 到受控源执行边界的自然入口已接通；真实源执行在 12.229 秒后以 `PIPELINE_EXECUTOR_FAILED` 终止、rowsWritten=0。没有 ingress、occurrence、dispatch attempt 或 BusinessInvestigationRun，因此不能声称真实数据更新已自然形成 Case/Run。

检测到首个源运行终态后，立即通过正式 PATCH 把 schedule 恢复 disabled；没有调用 POST run，没有第二次源读取，没有改写或删除失败运行。最终 running=0、unresolved=0、负租户 dispatch=0。

## 当前 L 权威与入口

- L installation `19620ea4-4a36-4cf1-a14a-8b24ee7d9fc3`，generation `64742c68-5e71-485b-a3c8-edc20be3d101`，epoch 3。
- Policy revision 8、hash `sha256:70f897d1c6ec1b9e71f9b8c01dee3207aa1ed2bb1ace29466e9810a93681278a`；Policy head 按事件控制设计保持 disabled，独立 automation binding revision 1 为 approved/enabled。
- 十条路由均为 L extension、group revision 37、unfenced；event-control revision 1，其余 revision 21。
- source selection `source-selection-3129cb60-f65d-40d2-a8db-3c30cd428647` revision 1；runtime control `pipeline-control-330b69b5-565d-4052-836d-c0f9ae236569` revision 1；schedule control binding revision 14。
- 独立 Runtime Host PID 87185 保持 `product-event` 与 `analysis-data-requirement` 两个 worker，canaryTenantCount=0；API 进程内 Host 禁用，真实 Cron 与独立 snapshot worker 启用。

## 真实失败事实与诊断边界

- Cron slot：`2026-09-16T16:00:00Z`；started `16:00:06.292626Z`；finished `16:00:18.540755Z`。
- 一次源调用 claim 已持久化，callOrdinal=1，绑定 L/current control；没有 pipeline runtime Receipt 或 durable ingress。
- API 日志只出现 `Opening SSH tunnel: auth=password`，没有出现 `SSH tunnel ready`；失败时长与 JDBC runtime 的 50×0.2 秒隧道就绪上限相符。
- `read_selected_snapshot` 当前会把连接器异常统一收敛为 `SELECTED_SNAPSHOT_READ_FAILED`，上层又持久化通用 `PIPELINE_EXECUTOR_FAILED`。因此现有持久证据只能确认“源读取前的通道未完成”，不能从数据库 Receipt 区分隧道未就绪、数据库认证或其他安全分类；不得凭推断重跑。

## 代码与验证

- 新增 L 固定 preflight、authority/policy/event-control profile、自然 API 启动器和 Cron-only arm/observe/disarm 执行器；通用 P02 授权窗默认仍为 15 分钟，L profile 明确 90 分钟。
- 执行器源码不含 schedule `/run` 调用；schedule 最终 disabled，私有 intent/result 保持 0600。
- L/J profile、自然门、事件消费者/分析服务相关累计回归 75 passed；新增自然与启动配置组合 13 passed；compile 与 diff check 通过。
- AR2-7 扫描 1981 / classified 198 / migrated 93；hash、前向依赖、跨层导入、动态引用为空。唯一反向调用者 `aos_api.ecommerce_event_proposal_gate` 是清册既有漂移，本波不修改清册掩盖。

权威只读快照为 `sc4-5l6y5f4-p-natural-product-event-final.json`。

## 下一波

进入 Y5f4-Q“源失败分类与自然恢复资格”：先在方案中固定可公开的连接失败码、嵌套异常分类传播、数据库持久化与 unknown/failed 恢复门，保留原通用脱敏正文；用专项及真实隔离测试证明不泄漏 endpoint/账号/密码。随后只读复核当前 SSH/JDBC 健康，并为新的自然 Cron 建立后继 authority/policy revision；本次 `scr-09fc7164153f4d7d` 保持不可变且不作为可恢复 saved-input run。新 Cron 仍只允许一次源调用，成功后才继续 occurrence → Case/Run → 分析数据补齐与三阶段经营参谋 worker 装配。
