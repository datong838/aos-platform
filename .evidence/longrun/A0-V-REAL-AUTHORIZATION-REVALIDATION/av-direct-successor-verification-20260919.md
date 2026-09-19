# AV 直接后继、路由切换与长续租验证

## 结果

AV installation `5f01eda8-ca5f-4892-8510-385704ccddb2`、generation
`17104053-f4c9-47e1-89b0-f3f353076dda` 已从 AU 的正式 detach Receipt
`7e223943-906f-4efe-8d4b-da7fc2424e48` 创建；父 Receipt content hash 为
`sha256:a3155cdf8c5fe13995faac9de8f6d8eedbf83609239303f09d9fcee8119bdfb1`。

AV installation lifecycle 四项 operation 均 succeeded；最终 Binding 为 rev6/epoch3、enabled、unfenced、
desired enabled、observed ready，三项运行资源均 pending/unreleased。配置为
`c55c7013-0baf-4a74-9b38-fb0d3f3798f9` rev1，hash
`sha256:b46b124703e956bae1a85713fb8b7058a6fb787b3656f50323841a2dfb51e4c0`。

Successor registration Receipt 为 `cbe62f06-fa4a-44c4-b7df-b4962889b844`，content hash
`sha256:85181180d472869501978e90a6be43da675546a7dd4cdd2e10a4f25c03468cfe`。固定 cutover operation
`9346c5d1-184d-44e0-a0ed-77b71c2d36c6` 完成 approve/prepare/pause/commit/validate/resume；prepare、commit、
validate、resume Receipt 分别为 `8549351f-e592-4905-b54e-beec3c3e89ef`、
`d25ac7bb-9534-404e-a381-85346f9d9a4a`、`7899c9fe-a7f9-439e-956e-f288596c1f55`、
`e64279b7-0585-4f89-a7b5-a7d63e64acdf`。终态九路均为 AV extension rev117/group144，claim 已恢复，
externalEffectsAllowed=false。

## Runtime Host 与连续观察

launchd `com.aos.a0v-runtime-u` 保持唯一进程 PID 8154，`pgrep` 只返回一个 Host；状态文件读回
`RUNTIME_HOST_ACTIVE`、tenantCount=1、canaryTenantCount=0、唯一 live target 为 AV，且
`recoverableStoreExecutionLimitSeconds=1800`。

只读健康观察以 6 次续租为基线，36 个样本从 2026-09-19T10:08:02Z 持续到 10:19:46Z，最终 renewals=18、
delta=12、last sequence=31；三资源 expiry 推进至 10:22:31Z。观察结束后的独立 final audit 为 renewals=19、
last sequence=32，Binding、资源与九路仍一致。

原始观察结果的 outcome 因机械继承标签残留写成 `AU_HEALTH_OBSERVATION_GREEN`，但其中 generation、资源与路由
均明确属于 AV。原文件保持不改；代码已修正为 `AV_HEALTH_OBSERVATION_GREEN`，并生成只增不改的派生校正证据
`health-observation-av-corrected-result.json`，记录 `labelCorrectionOnly=true` 与原标签。该缺陷未改变数据库或运行态。

## 安全边界

- definition 始终为 rev73 disabled，AV attempt=0；
- 全租户 running、unresolved、runtime pending 与 `dev-org/dev-project` canary 均为 0；
- 十二 Run 仍 running，十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending 均为 0；
- 未启动 18181、qcursor 或 snapshot worker，未读取商城源数据，未调用 `run_definition`；
- 230 L0 继续挂起，未 push，未修改 AU 与十二 Run 的既有记录。

## 验证与下一波

AV/AT/AU successor、retirement、recoverable Store 与 snapshot worker 累计回归 `76 passed`，Python 编译、差异检查、8434/18181
及唯一 Host 检查均在提交前重新采集。下一波只能先写 AV 保存快照恢复方案，再以纯 HTTP profile 禁用 Cron、
snapshot worker 与第二 Runtime Host，完成 frozen snapshot transfer/renew；取得新的 definition authority 后，才允许
关闭端口并由自然 worker 领取唯一 attempt，禁止手工执行 definition 或重发既有 Store 幂等键。
