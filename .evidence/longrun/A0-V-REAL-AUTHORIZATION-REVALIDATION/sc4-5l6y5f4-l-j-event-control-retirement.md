# Y5f4-L J 配置刷新后事件控制真实退场

日期：2026-09-16

结论：`A0V_Y5F4_J_EVENT_CONTROL_REFRESH_RETIREMENT_GREEN`

## 真实动作

1. 基于 J 代真实配置刷新 Receipt 和已禁用的 ProductEvent policy，生成独立 R2 fence 审批。
2. event-control fence 成功：Receipt `9563a232-0b45-4b9f-8b10-aabedacd4eba`，九路仍在 epoch 5，事件控制在 epoch 3 单独围栏，组版本汇合到 32；同键重放返回同一 Receipt。
3. 排空发现 12 条 `needs_attention/unknown` 旧 epoch 初始化。逐条核对目标幂等键：业务命令 Receipt=0、Investigation Run=0。
4. 新增并部署 a0v071。只有 fence Receipt 携带可验证的 Refresh Receipt 引用时，正式 UnacceptedAnalysisClosure 才允许当前 runtime 处于 refresh target epoch；旧无刷新路径不变。
5. 12 条初始化逐条生成不可变 closure Receipt，全部 `businessAccepted=false`；状态收敛为 `cancelled/closed_unaccepted`，没有重发业务命令。
6. 独立 R2 shrink 审批后，排空为 running=0、claimed=0、unknown=0；shrink Receipt `6086706a-6ba5-409a-ac6d-577059c4c09c`，事件控制行删除，九路保持 epoch 5 并推进到 group revision 33；同键重放返回同一 Receipt。

## 部署和验证

- a0v070 → a0v071 全新 clone 与主库迁移均保全 552 张既有表指纹；迁移阶段业务写入和源调用为 0。
- Alembic 单 head：a0v071。
- lifecycle + unaccepted closure PostgreSQL 回归：37 passed。
- 正租户最终为九条业务 dispatch、event-control=0；负租户可见行=0。
- runtime 仍为 revision 9 / epoch 5 / enabled / ready / unfenced，本波次未启动自然经营 Run。
- external effects=0，business accepted=0，business runs resumed=0。

## 下一步

进入下一波次：对九条业务路径执行正式 runtime disable、排空和 detach，证明 refresh 后仍可禁入与卸载；随后从不可变安装/配置权威受控恢复到 ready，不启动经营 Run。完成恢复后再进入真实商城变化自然触发的首链观察。
