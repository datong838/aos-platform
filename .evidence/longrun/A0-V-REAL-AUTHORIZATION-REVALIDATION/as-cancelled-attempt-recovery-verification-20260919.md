# AS 取消失败边界与暂停验证

## 结论

AS Runtime Host 长观察从基线 8 次续租推进到 20 次，新增 12 次且全过程 Binding rev6/epoch3
`enabled/unfenced/ready`、三资源健康、attempt=0，越过 AR 的瞬时陈旧观测故障点。

冻结输入随后以 `sourceReads=0` 转移：十二 schedule 禁用确认，十二套 source/control/binding 建立，definition
rev67(AR disabled) → rev68(AS disabled)，recovery rev21 → rev22，并生成 definition rev69 enabled。

临时恢复 18181 时使用的既有自然链 profile 同时启动 snapshot worker。rev69 启用后自然领取 attempt
`af7c1fc1-8283-40d7-ab62-f7d6145417c6`；临时 API 停止后，该 attempt 以 revision5、
`RECOVERABLE_INGRESS_CANCELLED / IngressJournalConflict` 失败。没有调用 `run_definition`，但这是一次真实失败，
不得记作保存快照成功。

## 失败边界与处置

- attempt 数量 1，operation key 与原 snapshot group 一致，原 Store idempotency key ordinal 为 `:1`；
- 十二 Run 仍 running，十二 Dataset Receipt、一个 relationship、一个 1168-link command 保持；
- retirement、link Store Receipt、`ecom_link`、link Outbox、projection pending 均为 0；
- 九路仍为 AS extension rev108/group135；三项资源健康；`dev-org/dev-project` canary 为 0；
- 新增只读 `a0v_as_attempt_guard.py`，实库输出 `FAILED_FREEZE_BOUNDARY`；
- `pause-failed` 在上述边界完全一致后，以唯一 CAS 把 definition rev69 推进为 rev70 disabled，阻止再次自然领取。

临时 18181 已停止；8434 浏览器页面仍可渲染缓存本体，明确显示“当前离线 · 仅可浏览已缓存内容 · 写操作已排队（0）”
和“aos-api 不可达”，页面未执行写操作。独立 Runtime Host PID 95647 与 caffeinate 保持运行。

## 验证

- AS guard + saved recovery 专项：14 passed；
- AS 安装/业务/切换、guard、saved recovery、recoverable Store 与 lease renewal 累计回归：66 passed；
- Python 编译与 `git diff --check` 通过；
- 方案/代码复审确认 guard 只有 SELECT，pause 只允许 exact rev69 → rev70，失败不授权重发。

## 下一波

以 definition rev70 disabled、唯一 failed attempt 和零 Store 副作用为前置，正式退休 AS installation/generation；
要求九路回 legacy、三资源释放、无 running/unknown/pending、canary0。随后从 exact detach Receipt 创建 AT direct
successor，并将后续临时 API profile 拆成纯 HTTP、关闭 qcursor/snapshot worker，避免在准备阶段提前领取。
