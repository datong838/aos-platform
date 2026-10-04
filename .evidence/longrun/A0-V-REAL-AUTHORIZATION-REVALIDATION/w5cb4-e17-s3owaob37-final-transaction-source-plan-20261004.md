# E17-s3o-w-ao-b37｜Capability 最终事务签名来源复核施工计划

## 上位方案与现状

- 231-2/3/4 与 BIND-1 规定：目录的 published Capability 只使绑定进入 provisioning；运行 readiness、激活与调用要重验当前签名安装、精确依赖、撤销和租户，不以先前快照授运行权。
- b36 的 `read_unique_active_installation_release_evidence` 已验证 0/多项禁入、唯一项签名/Registry/锁/字节复核，但它自行打开只读事务且明确返回 `EVIDENCE_ONLY_NO_START`。当前安装 approved3/active NULL，正式身份缺失。
- 原 `AipBindingReadinessService.evaluate_capability` 的 capability/route/policy/证据分别从 Reader 的新连接读取；`AipCapabilityBindingService.evaluate` 在写事务前读取，`update(...active)` 虽在写事务中重新调用 readiness，但该调用仍用独立 Reader 连接。issuer 的 UPDATE/Receipt 同事务没有当前签名安装重验，也无持有 source/撤销行锁。单纯注入 b36 返回值会留检查后撤销窗口。

## 文件级实施与 RED

1. 在 `services/aos-api/tests/extension_runtime/test_current_installation_release_evidence.py` 增可复用原事务的 Reader 负例：已存在但非 active 当前安装、错 hash、跨租户、多候选；验证传入连接不由 Reader commit/关闭，结果仍为 evidence-only。先跑目标 RED。
2. 在 `services/aos-api/aos_api/extension_runtime/current_installation_release_evidence.py` 仅抽出 b36 唯一选择与原 `_read_exact_in_transaction` 复核为内部 `..._in_transaction` 原语；原公开只读包装行为保持。传入连接的调用方负责事务隔离/锁与权限；不能将此原语直接当 active/run 授权。
3. 在 `services/aos-api/tests/aip/test_aip_binding_readiness_service.py` 固定当前激活缺最终签名来源的严格失败用例。若不新增当前生产低权限身份/授权和源撤销锁就不能完成同事务正向，保留 strict xfail，下一波精确实现 issuer/Reader 同事务及最终调用门；不靠高权限 owner 或 test-only 正向消除 xfail。

## 验证与禁区

- 专项/相邻：当前签名只读 Reader、隔离 Growth1.13 full-schema OCI、BIND-1 就绪/激活测试；避免两个 full-schema 测试同时迁移全局 PG 角色，串行执行。py_compile、diff check 和方案/代码一致性复审。
- 本波不更改当前库/schema/Host/worker/Provider、不发布 Growth1.13、不改原用户可见 Catalog、Receipt/Binding 合同。b34 原 strict xfail 和当前实例禁入不变；若原语不足以安全接线，明确留下最终事务缺口，不伪称首链。
