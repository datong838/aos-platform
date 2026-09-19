# AU 直继切换、1800 秒装载与陈旧健康冻结验证

## 结论

AU 已从 AT 的 exact detach Receipt 完成 installation、配置、successor registration 与九路 cutover，但长续租门禁
未通过，不能记作 GREEN。Runtime Host 正式重载前，AU runtime-apply 的 Health observation 已过期；新 Host 启动后，
正式 owner 将 AU 推进为 Binding rev7/epoch4、disabled/fenced、observed unknown，三项资源 released。

definition 全程保持 rev73 disabled，AU attempt=0；没有调用 `run_definition`，没有读取商城源数据，没有产生 Store
写入或未知结果重发。当前安全结论为 `AU_STALE_HEALTH_FREEZE_BOUNDARY`，下一波必须正式退休 AU，再从 exact detach
Receipt 创建 AV；不得在 AU 内重新 enable 或重放 cutover。

## 安装、登记与切换证据

- AT disable operation：`5d69615c-2e9f-4ad5-8725-14a9e1fefd76`；detach Receipt：
  `3046e81b-fedb-4431-9493-ff79bc50820b`；content hash：
  `sha256:dc09ee0ceb07994f37641f6fa7b9a8f2caec0229faaf58028c00a6bb83297322`。
- AU installation：`eddc89f9-1e91-4e42-be4e-7d81dc941c1d`；generation：
  `01a5eb0a-f41f-40f7-ba00-b5db23a7806f`；lock：
  `sha256:6192980457e1ff735b57af6352f0e60f989f6d566830a2d690641dd5035fa60f`。
- configuration：`2a593faf-03a0-44ab-b534-5c8a8dd43cc0`，hash
  `sha256:369e7206d9642fb77ca7aca55683f9ce837a7b506bbcedbaac40bd39b4984593`；四项 installation
  operation 在切换前均 succeeded。
- successor registration Receipt：`64531fa6-8fe0-460b-997d-c8d54b4fe8ee`，content hash
  `sha256:e34258040635aaf797fedb5bfff3a07e17f260191c6410ec2bf641c39918c98a`，登记时 executable=false。
- cutover operation：`30f30143-f8d0-4ae5-b2bc-6dbbf681f08c`；prepare/commit/validate/resume Receipt 分别为
  `e68eed28-7b21-48d2-9844-dcdf0c25c418`、`0dd8ab1e-2ffa-4568-ae4f-7e0be1161d20`、
  `23e6ce4c-95bf-40c9-bd17-13a3915c24c4`、`d27b5951-c7fb-4c99-b78c-3d8e71d76eed`。
- 九路由从 legacy rev113/group140 切为 AU extension rev114/group141；pause/commit/validate/resume 全程
  claimed、unknown 与 running attempt 均为 0。

## 1800 秒修复装载与失败边界

- 受 launchd 管理的唯一 Host label 为 `com.aos.a0v-runtime-u`。直接 SIGTERM 后 supervisor 自动恢复单实例；随后用
  正式 `launchctl kickstart -k` 重载，最终唯一 PID 为 8154，没有启动第二 Host。
- Runtime Host 状态新增代码级读回字段 `recoverableStoreExecutionLimitSeconds`；新进程返回
  `RUNTIME_HOST_ACTIVE`、该字段为 1800、tenantCount=1、canaryTenantCount=0、liveTargets=[]。
- AU 终态：Binding rev7/epoch4 disabled/fenced/observed unknown，资源 3/3 released；九路仍指向 AU
  rev114/group141，故尚未达到正式 retirement/detach。
- 最新只读核账：AU routes=9、attempts=0、全租户 running=0、unresolved=0、runtime pending=0、
  definition rev73 disabled、`dev-org/dev-project` canary=0。

## 验证与风险

- AU replacement/successor/cutover/health 专项在登记前通过 `5 passed`；Runtime Host、recoverable Store 与
  snapshot worker lifecycle 累计通过 `35 passed`。
- Python 编译与 `git diff --check` 通过；本波代码只增加 direct-successor 精确身份/Receipt 门禁和 Runtime Host
  执行上限公开读回，不改变 Store 幂等键、租户范围、外部效果策略或失败重发规则。
- 风险仍为 AU 九路已切换但 binding 已被健康门禁 fence；虽然 definition disabled 保证 snapshot 不会领取，仍须
  下一波先走正式 disable Owner 的 fence/detach，不能直接创建 AV 或重新启用 AU。

## 下一波

先新增 AU stale-health retirement plan 与只读 guard，锁定 rev7/epoch4、三资源 released、九路 rev114/group141、
attempt=0、definition rev73 disabled、零 in-flight/canary。随后以唯一 disable operation 完成正式 fence/detach，要求九路
回 legacy rev116/group143；verification 落盘并提交后，再以 exact detach Receipt 创建 AV direct successor。
