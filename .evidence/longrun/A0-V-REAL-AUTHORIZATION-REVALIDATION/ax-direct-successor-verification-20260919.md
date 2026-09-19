# AX 直接后继、路由切换与长续租验证

## 结果

AX installation `be884663-0dba-4d9b-aa56-84caaf01147d`、generation
`a14c911b-6796-4d22-a3b0-1817cf502de9` 已从 AW 的正式 detach Receipt
`0c50775b-62fe-4251-81f4-3c9a8709a90e` 创建。安装生命周期四项 operation 均 succeeded；配置
`0e59aa44-bda5-43db-930d-b77bb7b02d32` rev1/hash
`sha256:f2ed99032b03af6f2855b39e513ad5117fc1fdd2797927c77d9f4d485fda9bb2` 明确引用 current
runtimePolicy rev9。Binding 最终为 rev6/epoch3、enabled、unfenced、desired enabled、observed ready，三项资源
pending/unreleased。

Successor registration Receipt 为 `b5304d33-63f2-401a-a7fd-e6ed0c313f07`，content hash
`sha256:d8641d862f190da4f35ddb8a307b57d148b4b94f8bc2d7b031d36a6f5785d59d`。固定 cutover operation
`900ed51b-9c97-424b-9a19-5e4dc2868f66` 依次完成 approve/prepare/pause/commit/validate/resume；resume Receipt
`573e8776-e4b4-4dd0-af44-0393572723cc`，hash
`sha256:1725e83ece7e307b61e9eb7d2b3ee43179123a123bfd005e61587c7cd78743e9`。最终九路均为 AX
extension rev123/group150，claim 已恢复，外部效果保持关闭。

## 连续观察

只读观察从 5 次 `runtime_lease_renewed` 基线推进到 17 次，新增 12 次；采集 37 个样本，起止为
2026-09-19T12:11:52Z 至 12:23:57Z。终态 last sequence=30，三资源 expiry 均推进至
2026-09-19T12:26:43Z；全过程 AX attempt=0、全租户 running/unresolved/runtime pending=0、九路 exact=9、
`dev-org/dev-project` canary=0。私有终态证据为
`.aos-recovery-20260919/state/q-advisor-baseline/replacement-ax/health-observation-result.json`，权限 0600。

## 保存快照与无副作用边界

definition 保持 rev76 disabled；十二 Run 仍 running，十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、
projection pending 全零。未启动 18181、qcursor 或 snapshot worker，未读取商城源数据，未调用 `run_definition`，
未重发任何 Store 幂等键。

## 验证

- AX replacement/registration/cutover/health 与 AW/AS 相关回归：`11 passed`；
- Python 编译、差异检查通过；
- 方案与执行一致：installation/generation/config/predecessor Receipt、旧组 revision 与 operation ID 全部固定，
  current runtimePolicy rev9 已由配置本身读回，未知结果只读核账且不重发。

## 下一波

新增 AX 保存快照恢复方案：纯 HTTP 18181 显式关闭 Cron、snapshot worker 与进程内 Runtime Host；先完成十二
schedule disabled 配置，再以 sourceReads=0 将 definition rev76(AW disabled) 转移为 rev77(AX disabled)，从
recovery rev24 续签到 rev25 并产生 definition rev78 enabled。关闭端口后才允许既有自然 worker 领取唯一 AX
attempt；1800 秒有界观察规则保持，不手工执行 definition，不 push，230 L0 继续挂起。
