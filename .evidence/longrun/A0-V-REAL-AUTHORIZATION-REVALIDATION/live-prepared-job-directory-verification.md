# Live PreparedJob 目录验证

日期：2026-09-12

基线：`78af8d63`

结论：进程内目录现在可以按真实 job 派生的 TenantScope/Installation/generation 唯一登记和查找
`PreparedJob`；consumer 对 owner 的持有期与目录可见期一致。该目录本身不代表调用授权。

## 验证

- Red：目录模块不存在时测试 collection 明确失败。
- Green：exact resolve、跨租户/错 Installation/错 generation 拒绝、竞争 owner 拒绝、同 owner 幂等、
  identity-bound unregister，以及 consumer 登记/关闭撤销全部通过，`6 passed`。
- 既有 preparation consumer 隔离 PG 专项在未设置显式开关时保持跳过，没有以 mock 结果冒充 PG 证据。
- 累计 directory/owner/consumer/worker/stage-review transport 回归：`37 passed, 30 skipped`。
- AR2-7 closure：扫描 1780、分类 146、迁移 93；所有错误数组为空。
- `git diff --check` 通过；无新数据库表、无运行时启动、无 package/Installation/租户数据变化。

## SHA256

- directory：`9c211d1228587d297572b3de7b37500ac24e1b0ffde3d59d6bc05654df42207e`
- consumer：`fc4d1e0deacd13dd2252c66c005eba9686b39f0c681592f0f61346d300278de1`
- tests：`b1fba96a76b6ee6155bdcdda8272ce7ba7e097af728cabdc988d7a426d666396`
- plan：`e23472d007e2e15a129c4baa62910d645fa82c507835ff2433eccd1ad0fed293`

## 下一门

增加 `CurrentInstalledInvocationAuthority`：从数据库读取 active Installation/binding/lock 的精确快照，
用目录取得同代际 live job，在 IPC 前后分别重读并 exact 比较；漂移时丢弃响应并拒绝。随后才将其
包装为 stage-review service 的 `invoke_installed_once`。
