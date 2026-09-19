# AW 直接后继、路由切换与长续租验证

## 结果

AW installation `f94b9425-9bc4-4369-8ae3-138c50c9ab81`、generation
`a92f7bb2-3d90-4d88-9632-5fc9a70bd650` 已从 AV 的正式 detach Receipt
`eed47855-2a96-4709-be2b-8283422a180a` 创建；父 Receipt content hash 为
`sha256:9b60c491ad0476127c95740ab7f32276de6bb1ebeaf063326e70fe5a28f757ca`。

AW lock hash 为 `sha256:f5e2bc370faaaecfc61498af1eac856ba6e4f17c77e6df84aded0bc0ade8ccd3`。
installation lifecycle 四项 operation 均 succeeded：runtime apply
`a0c9eed6-ab85-41eb-94e0-7eea26551b64`、runtime verify
`67e1ea7f-67b8-4959-ad05-5cadb80d97b1`、configure
`567b7057-0993-466e-b3fb-cb487fa07d00`、enable
`3ced94bb-b899-4015-bd62-ada9bb98d1d7`。最终 Binding 为 rev6/epoch3、enabled、unfenced、
desired enabled、observed ready，三项运行资源均 pending/unreleased。配置为
`ad97cf60-eeb3-4938-803e-31ca8b7458f1` rev1，hash
`sha256:c6930d1ae14b26953338f60c7ff1ff644fc79e6764eaf13407af499bef5e7948`。

Successor registration Receipt 为 `7460a214-ac14-4bcf-8657-a21e47f24f12`，content hash
`sha256:c439e220f03aadb492edc692d2742ca98b73b3960ea1074c524cd5d7b21cdfee`，request hash
`sha256:a753f58a283062a92fb06f47fa9cf19869e1644888bf642b34b2d089beaba732`。固定 cutover operation
`255d4a17-0ec9-4506-a1a9-f3337103f832` 完成 approve/prepare/pause/commit/validate/resume；prepare、pause、
commit、validate、resume Receipt 分别为 `fc0f19fc-5425-422d-80af-b9a0e2b6a8f1`、
`da59861c-caa3-4992-a983-32efd7d4b6f3`、`f936ae83-e54b-40d6-a8f8-8a6cfd0e429f`、
`3a695829-7603-4b4f-8535-af8cc68f06d2`、`00b58846-48ac-4408-b8e6-8451643890a8`。终态九路均为
AW extension rev120/group147，claim 已恢复，externalEffectsAllowed=false。

## Runtime Host 与连续观察

launchd `com.aos.a0v-runtime-u` 保持唯一进程 PID 8154；状态文件读回 `RUNTIME_HOST_ACTIVE`、tenantCount=1、
canaryTenantCount=0、唯一 live target 为 AW，且 `recoverableStoreExecutionLimitSeconds=1800`。8434 仍由既有
Node 服务监听，18181 无监听；未启动第二 Runtime Host。

只读健康观察以 9 次续租为基线，41 个样本从 2026-09-19T11:34:15Z 持续到 11:44:20Z，最终
renewals=21、delta=12、last sequence=34；三资源 expiry 推进至 11:47:16Z。结果 outcome 为
`AW_HEALTH_OBSERVATION_GREEN`。

## 安全边界与执行偏差

- definition 始终为 rev76 disabled，AW attempt=0；
- 全租户 running、unresolved、runtime pending 与 `dev-org/dev-project` canary 均为 0；
- 十二 Run 仍 running，十二 Dataset Receipt 保留；Store Receipt、`ecom_link`、projection pending 均为 0；
- 未启动 18181、qcursor 或 snapshot worker，未读取商城源数据，未调用 `run_definition`；
- 230 L0 继续挂起，未 push，未修改 AV 唯一 abandoned attempt 与十二 Run 的既有记录；
- 首次 replacement prepare 因沿用 `av` label 的本地幂等冲突在写入前失败；抽取固定 label 后成功；
- 首次 verify 在 Host 尚未完成 apply 时于写入前失败，等待读回 operation succeeded 后才正式 verify；
- 首次 cutover approve 因 AW wrapper 缺少基础执行器兼容别名而在 intent/审批写入前失败；补齐只读别名并
  通过回归后才正式 approve。三项均没有未知提交边界、没有重发已提交 operation。

## 验证与下一波

AW/AV replacement、successor、cutover、health 专项回归 `9 passed`，八个执行器 Python 编译通过，
`git diff --check` 通过；唯一 Host、8434/18181、1800 秒上限均在提交前重新采集。

下一波只能先写 AW 保存快照恢复方案，再以纯 HTTP profile 禁用 Cron、snapshot worker 与第二 Runtime Host，
完成 frozen snapshot transfer/renew；取得新的 recovery/definition authority 后，才允许关闭端口并由自然 worker
领取唯一 attempt。任何未知结果先冻结边界，禁止手工执行 definition 或重发既有 Store 幂等键。
