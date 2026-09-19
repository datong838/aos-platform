# AT 直接后继、路由切换与长续租验证

## 结果

AT installation `631e6d01-a5bb-4865-95eb-07d5665ed957`、generation
`63ea2c87-f185-4b02-b792-1e3073db4a1b` 已从 AS 的正式 detach Receipt
`ae435475-8932-444b-ab41-9660fb966eaf` 创建。安装生命周期四项 operation 均 succeeded；Binding 最终为
rev6/epoch3、enabled、unfenced、desired enabled、observed ready，三项运行资源均 pending/unreleased。

Successor registration Receipt 为 `d95efc1b-d1bd-4c00-8870-47914c858a35`，content hash
`sha256:6052594c79e0de0b4115bf255714524dd2f968475cf788da66d100276a0f3ab0`。固定 cutover operation
`4062239f-18d4-40a2-990f-64ddbea8e9a6` 依次完成 approve/prepare/pause/commit/validate/resume；最终九路均为
AT extension revision111/group138，claim 已恢复，外部效果保持关闭。

## 连续观察

只读观察从 6 次 `runtime_lease_renewed` 基线推进到 18 次，新增 12 次；观察器共采集 31 个样本，起止为
2026-09-19T08:30:58Z 至 08:41:02Z。终态 last sequence=31，三资源 expiry 均推进至
2026-09-19T08:43:51Z；全过程 AT attempt=0、全租户 running/unresolved/runtime pending=0、九路 exact=9、
`dev-org/dev-project` canary=0。私有终态证据为
`.aos-recovery-20260919/state/q-advisor-baseline/replacement-at/health-observation-result.json`，权限 0600。

## 浏览器与边界

8434 本体页面只读验收可渲染缓存对象；页面明确显示当前离线、aos-api health HTTP 500、写队列 0，电商工作台目录
因 API 离线暂不可见。本波未启动 18181、qcursor 或 snapshot worker，未点击写操作，definition 保持 rev70 disabled，
未读取商城源数据，未调用 `run_definition`。

## 验证

- AT/AS 安装、登记、cutover、健康观察、失败退休、recoverable Store 与 lease 累计回归 `72 passed`；
- 方案与代码一致：所有 installation/generation/config/predecessor Receipt、旧组 revision 与 operation ID 固定；
- 私有 intent/result 均为 0600，未知结果只读核账且不重发；
- 累计回归、Python 编译及差异检查结果在本提交前重新采集。

## 下一波

新增 AT 保存快照恢复方案：受控 18181 显式关闭 QYH Cron、snapshot group worker 与第二 Runtime Host，只用于十二
schedule 禁用配置；随后以 sourceReads=0 将 definition rev70(AS disabled) 转移为 rev71(AT disabled)，从 recovery
rev22 续签到 rev23 并产生 definition rev72 enabled。完成 authority 后才启动并持续保活自然 worker，观察唯一 AT attempt，
不得手工执行 definition 或重发原 Store 幂等键。
