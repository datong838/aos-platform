# 阶段评审内部异步 service 验证

日期：2026-09-12

基线：`efcade78`

结论：内部 async service 已把 Receipt replay fast path 与五门新发布双事务装配完成；尚未绑定真实 installed invocation factory 或公开入口。

## 验证

- 新发布顺序为 replay preflight（无 Receipt）→ prepare/composite → 五次 one-shot IPC → current/publish，真实隔离 PG 可由 StageDecision Owner exact 回读。
- 同命令 replay 命中 Receipt 后 proof reader 与 IPC 均零新增；合法重算 hash 但 body 不同的 replay 在 Owner exact 对比拒绝，同样零新增调用。
- IPC TimeoutError 原样上抛，StageDecision head 为零，不重试。
- Owner replay 使用与新发布相同 target/key advisory locks，检查 typed item、expectedVersion 和 Receipt exact result。
- 定向初测 `6 passed`；增加 replay body conflict 后相关全链 `91 passed`；两个模块 compileall 与 diff check 通过。既有 warning/logging 提示未由本波引入。
- AR2-7 closure 扫描 1779、分类 142、迁移 93；所有错误数组为空。

## SHA256

- async service：`918354d7f1415a046cee7a419a101910ad1a8a3ff67e6c399b279e0847f18262`
- Owner binding：`4422194578103acf404892eb83ecdb8805b530fb5cb91e9e05a8064451d32142`
- tests：`1f1f95b4957f498da8c827087a2b4678ffd8117aef60cef42e61ea4de80da5b7`
- plan：`cb3c2709835a9db91fccfa17f2bd882848085c691901d7afa46a1cbea17e08fd`

## 下一门

复核 extension runtime 的真实 installed session 调用工厂与当前 1.4.0/未来 1.5.0 版本边界；增加内部 composition factory。当前 service 没有路由，不能据此声称真实租户已可评审。
