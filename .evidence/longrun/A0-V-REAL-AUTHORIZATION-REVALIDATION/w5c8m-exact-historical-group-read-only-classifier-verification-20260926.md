# W5c8m｜精确单组历史见证只读分类验证

## 判定

本波**隔离 PG 单组只读候选分类 GREEN，真实全量扫描/回填/ACK 未授权**。先行方案 `m1@2e1691de`，补充收敛 `m1@27530103`：保留 W5c8l sidecar 对运行角色的 SELECT 停线，本波只读原 claim/input/member。真实库未迁 a0v_096/097、真实 profile 停止，原 12 Run 当前状态未知。

## 第 1/9—9/9 步

1. 复习 W5c8g/j/k/l、`a0v_045/097`、原 Locator、只读 runtime 连接合同与 AOS-000674/m1。
2. 文件级方案先提交，并在编码前把 sidecar 查询/权限扩大从范围移除。
3. 新测试先因分类模块不存在 RED（collection `ModuleNotFoundError`）。
4. 最小分类器输入精确 `TenantScope`/UUID/已开启的 `REPEATABLE READ READ ONLY` runtime 事务；核当前 role/GUC、同租户原 claim/input、原 hash、binding schema/内嵌租户/actor、manifest 与按 ordinal 最多 13 个成员。返回枚举与 group UUID，不返回 JSON/文本见证或执行授权；无 source/sidecar/Worker/ACK 调用。
5. 原保存组 PG：正确组 `READY_CANDIDATE`，错误 UUID/`dev-org` 无组，可写连接拒绝，`1 passed`；纯行集注入：缺组/缺 input/hash 漂移/成员序漂移/13 成员拒绝，`1 passed`。严格字段复审后全文件 `2 passed, 7 warnings in 120.05s`；W5c8i–m 相关短累计 `32 passed, 3 deselected, 7 warnings in 10.69s`。`py_compile`、`git diff --check` 通过，disposable `aos_test_*` 数据库数 0。
6. 本波无 UI 改动；真实租户目录此前不可用，IAB localhost 上波被客户端阻断。本波未取得浏览器业务页验收，**不可判真实 UI GREEN**；未进行业务点击/商城源读取。
7. 复审：`READY_CANDIDATE` 只表示限定历史组在只读快照中可重建，未核 PREPARING/Occurrence/Origin、Host、双 Receipt、sidecar 或 fleet；缺 input/hash/member 的负例仅为纯行集注入，非 PG 持久表篡改证明。真实历史全量未扫，不能给 writer/ACK 授权。
8. verification 与代码在 m1 提交；D-waves/AOS CAS/Prime 回读另提交。`automaticAction=false`、`closureAuthorized=false`、`topologyComplete=false` 不变。
9. 自动进入 W5c8n：先设计**有界多组**只读分页/拒绝式计数报告，在隔离 PG 验游标、并发和租户边界；真实扫描与受控 writer 分别另门。

230 L0 挂起，商城源不读，unknown 不重发/不手工 `run_definition`；dev-org 仅零 canary，m1 单写不 push、不动其他分支。
