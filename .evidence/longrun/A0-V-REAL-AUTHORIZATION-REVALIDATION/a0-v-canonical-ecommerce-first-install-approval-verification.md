# A0-V Canonical 电商包首装组合与批准验证

## 结论

2026-09-10 在隔离恢复库 `aos-a0v-recovery-pg/aos_meta_head` 完成 Canonical 电商包的无 baseline 首次组合和双人批准。结果为 `CANONICAL_INSTALLATION_APPROVED`，重放精确命中同一 composition、installation、lock 与四类审查摘要，没有创建第二个对象或新增状态迁移。

本阶段只完成 Registry 后的 Composition/Installation 控制面，不包含 runtime apply、容器启动、schema Receipt 登记、configure、enable、Provider 调用或外部业务写入。

## 固定对象

- composition：`f58647ac-56a9-4739-898a-ba412c400f9f`
- installation：`c1eb714f-56de-4f28-ba06-c3440b3d18cb`
- installation state/revision/etag：`approved / 3 / 3`
- maker：`a0v-canonical-ecommerce-first-install-maker`
- checker：`a0v-canonical-ecommerce-first-install-checker`
- lock revision/hash：`1 / sha256:569f57bfa137fc146cebbbba0d617b3216698fd0eed2280677f2b06f77c1311a`
- resolved：4 个 exact bundle version、3 条 dependency edge
- contribution：16 项，其中 8 个电商主工作台模块
- permission diff：`sha256:d310d873b7fdb3d8adc8f6689156883cb8fb5d9a0b95f566d9541851a731bd20`
- migration plan：`sha256:9c790a19ae8d670812bcd5382cd9f49744650f9a7ca95da2f387b067705ec575`
- contribution diff：`sha256:f03cb321aeeadb66589ca8e8d35872d03f6f051d0a73ab28799ce2b06bc212c2`

## 首次与重放

- 首次有效续跑执行 `submit + approve`，installation mutation count 为 2；此前失败尝试已经创建的 draft 被安全复用。
- 重放返回相同 composition/installation、相同 lock 和审查摘要，`transitions=[]`、installation mutation count 为 0。
- 正向租户仍只有 1 个 composition、1 个 installation；runtime operation/binding 均为 0。
- 负向 canary `dev-org/dev-project` 的 installation/runtime operation/runtime binding 均为 0。
- 两次均记录 Provider invocation 0、external publication 0。

## 失败关闭与修正

1. 首次提交曾由 ordinary `InstallationRevalidator` 路径拒绝 runtime release。该拒绝发生在 runtime operation 之前，证明 legacy 安装重验证没有被绕过；随后改为既有 `RuntimeReleaseRevalidator` 权威。
2. 第一次修正把 runtime revalidator import 放在错误作用域，脚本以 `NameError` 退出；没有产生 runtime operation、binding 或容器。
3. import 作用域修正后使用同一 installation 恢复，不删除已审计 draft，不另建安装。

## 证据

- 首次结果：`a0-v-canonical-ecommerce-first-install-approved-result.json`
  - SHA-256：`13d4cbf758b164a771ebd8c828e8ae46760917f8274861c2aeeb0f4376ce2a31`
- 重放结果：`a0-v-canonical-ecommerce-first-install-approved-replay-result.json`
  - SHA-256：`6d036c2f6f33c051a55eee55bcb6b66c33e948b30c81b82eb8ccacecc1782b37`
- 隔离库逻辑备份继续固定为：`sha256:e438ba650162674a4215385d0f223d9043af22b6e4a6164c088f7cb2bfb35916`

## 下一门

下一步是 `runtime apply/verify`：先以 maintainer 权限将三个签名 `schema-requirements.json` 与当前 `a0v_001`/relation 事实绑定为幂等 Schema Receipt，再以 `RuntimeLifecycleService + PreparationWorker` 启动三个 exact OCI 并验证 registration。任何多成员 artifact 路由不明确、容器隔离不满足、schema 漂移或 partial generation 都必须失败关闭。

本结论不是 `A0V_CANONICAL_ECOMMERCE_FIRST_INSTALL_RUNTIME_READY_GREEN`，也不是 A0-V 总体 GREEN。
