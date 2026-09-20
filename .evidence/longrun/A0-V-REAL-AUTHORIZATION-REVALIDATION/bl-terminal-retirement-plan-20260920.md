# BL 单终态正式退休方案

## 当前权威

BL installation `ac9b3ec8-68ad-4e05-9f30-b2f8f6a473bc` / generation
`116d12fc-93bc-4071-a973-fdc6830ea8b1` 仍为 active；Binding rev6/epoch3 enabled/ready/unfenced，
三资源 live，九路 extension rev162/group189。definition rev118 disabled，18181、Runtime Host、snapshot
worker 与 supervisor 均为零。

唯一 attempt `06352972-8c80-4291-aece-2474209e6a76` 为 revision46
`abandoned / ATTEMPT_LEASE_EXPIRED / null`。十二 Run 仍 running、十二 Dataset Receipt 保留；Store Receipt、
`ecom_link`、outbox、projection pending 与 canary 均为0。本波只接受该 exact 边界。

## 文件级清单与顺序

1. 新增 `scripts/a0v_bl_terminal_retirement.py`：只注入 BL exact 身份、lock、单 terminal attempt、
   definition rev118、active rev162/group189 与预期 detached rev164/group191；复用正式 AQ
   `preflight → request-disable → process-disable → audit` Owner 路径。
2. 新增专项测试，固定常量、唯一 disable delivery、零 Store 边界和禁止 `run_definition`。
3. 串行执行四步；每步冻结结果。request 只接受 Binding rev6/etag5，process 只接受同一 operation，
   不更换幂等键，不重发 disable。
4. verification 落盘并提交后，才允许规划 BM direct successor。

## credential 丢失限制与恢复设计门

旧受保护 credential reference 与已签名运行目录在 BL 观察窗内被外部移除。preflight 可使用既有数据库
只读连接完成；若 request/process 的正常组合入口因该缺失 fail-closed，禁止伪造旧文件或降低校验。
必须先补充方案与专项测试，仅允许使用原 lifecycle/disable Owner、runtime role 与 exact 当前数据库权威；
不得直接 SQL 改写 Binding、route、Receipt 或资源状态。资源释放若依赖 Host，只能另立运行材料重建方案。

正常 `request-disable` 已在数据库写入前以 `CREDENTIAL_FILE_INVALID` 停止，并留下 exact intent。恢复适配器
只把容器内既有数据库连接转换成 `aos_runtime` session，构造原 `PostgresInstallationStore`、只读
`InstallationService.get` 与 `RuntimeDisableService`；disable 负向操作不需要重新验证已丢失的 release 文件。
适配器必须复用已冻结 intent/幂等键，并在调用前后执行 shared retirement snapshot；不得直接写表。
`process-disable` 同样只允许原 `RuntimeDisableConsumer` 领取一次 accepted operation 并调用
`finish_claimed`；eventId 在执行前冻结。核心完成后预期 Binding rev8/epoch4 fenced/disabled、九路 legacy
rev164/group191、fence/detach Receipt 各一，但资源可暂为 pending；资源释放必须再经原 reconciler 方案，
不得由适配器直接更新。

核心 disable 已提交后，三资源为 exact `pending/observed_release=false`。只允许调用原
`RuntimeUninstallCleanupExecutor`，配合 `CleanupOnlyOciDriver(OciDriver('colima-aos-extension'))`；该 Owner
在触碰 OCI 前冻结 uncertain checkpoint，并按持久化 resource owner、name、containerId 校验和删除。
三项结果必须均为 `released`，不得使用通用 docker 删除命令。完成后正常 shared `process-disable` 只能走
`recoveredAfterCommit` 只读分支，再执行 audit。

现场三项容器在 first cleanup 前已不存在，因此 uninstall Owner 按 unknown-outcome 规则先固定为
`uncertain`，未把 absence 当作释放证据。三项 Lease 已过期，且 name/containerId 双标识只读检查均 absent；
后续只允许原 `ExpiredResourceRecovery` 调用 `confirm_absent` 后记录 released。不得直接改资源 journal。
若 first uncertain checkpoint 将原 runtime-apply 标记为 `needs_attention/RESOURCE_CLEANUP_UNCERTAIN`，在三资源
全部 released 后只允许对精确 apply operation 调用原 `settle_committed_cleanup`。有已 fencing 的 Binding 时，
预期该历史 apply 终态为 `failed/PREPARED_RUNTIME_RELEASED`，不得复活 generation。

## 完成与停止条件

- 任一 attempt/definition/route/resource/hash 漂移立即停止；未知 Receipt 只读对账，不换键。
- audit 必须为 Binding rev8/epoch4 disabled/fenced/unknown、三资源 released、九路 legacy
  rev164/group191、fence+detach 两张 Receipt、definition rev118 disabled、唯一 terminal history和零副作用。
- 不启动 snapshot worker，不创建第二 attempt，不读取商城源数据，不 push，不改其他分支；230 L0继续挂起。
