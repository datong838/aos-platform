# E17 s3o-w-ao-b45：受限最终事务命令合同与第一施工点

## 复习结果

- 231-3 的 runtime 准入要求安装当前 active 指针、binding revision、权限/预算/策略在执行前仍有效；BIND-1 §5 要求 exact published 来源和激活事务内重算。b44 的真实 disposable PG RED 已证 test-only issuer 能绕过 Python readiness，直接伪造合法外形 evaluate+Receipt。
- `AipCapabilityBindingService.evaluate` 在 issuer 事务前调用 `AipBindingReadinessService`；`update(active)` 虽在 issuer 事务中调用，却由 `PostgresBindingDependencyAuthority`、`AipModelRuntimeStore/Resolver` 各自开连接。`current_installation_release_evidence._read_unique_active_in_transaction` 已允许调用方事务重验签名来源，但不授运行权。b41 的 test-only `SECURITY DEFINER` 证明安装行锁可在不授表 UPDATE 的情况下委托。

## 文件级施工顺序

1. **同连接读证据切片**：`aip_binding_readiness_service.py`、`aip_model_runtime_store.py` 及原子 Reader 仅在显式调用方事务时复用一条连接；保留原默认连接路径。先在 disposable PG 加失败测试：各依赖 Reader/Model resolver 不能在同一事务看不到调用方未提交的合法修订，也不能开第二连接。最小实现采用显式事务绑定构造，不用全局连接、可写 GUC 或 owner 绕过。
2. **受限命令负门**：在 disposable 完整迁移库以随机非 owner 发行/运行角色证明直接 Binding/Receipt DML、无 EXECUTE、跨租户、错版、双 Receipt、旧签名/撤销竞态拒绝。设计 DB 命令只接受 exact 输入，锁安装/Registry当前源后由可信同连接 evaluator 形成不可伪造来源，并与 Binding CAS/Receipt 一次提交；不能让发行角色同时拥有可直接伪造的表 UPDATE。若 SQL 内无法完整重算 Python 的模型/预算依赖，必须把可信 evaluator 与 DB command 的证明协议说清后再实现，不以“同连接”冒充完整防伪。
3. 仅在上述合同经克隆证明且 b25 operation guard、b41 安装锁函数合并后设计唯一 `a0v_136`。提交生产迁移与当前权威库切换须另波执行新一致备份、全恢复、零执行窗口和正式凭据核验；保持代码/库135对齐以维护每日最新栈。

## 验收边界

本波不能启 Host/worker/Provider，也不能消除 b34/b37/b44 strict xfail，直到 exact source、评估来源、CAS/Receipt 均在最终事务经非 owner 正反证明。`org-org/dev-project` 是唯一正向租户，`dev-org` 零副作用；当前真实库只读、不读商城源、不回放旧12Run、不手工 run_definition、不碰230 L0、不 push。配置/产品绑定可独立推进。
