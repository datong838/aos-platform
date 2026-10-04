# E17-s3o-w-ao-b34｜Capability 来源证据 Reader 与未闭合运行门

## 方案与 RED

- 依 b34 文件级计划复核 BIND-1 与 231-2/3：create 的 published Catalog 只形成 provisioning；active/runnable 才需要当前签名来源、安装代次和最终 runtime gate。不能在 create 直接强制当前 Growth1.13 active。
- `AipBindingReadinessService.evaluate_capability` 在其他依赖可用时未核 Catalog 签名来源。新负例传入失效来源 Reader，原结果 `AVAILABLE` 而预期 `BLOCKED`，单项 exit1；以 strict xfail 保存为正式来源未接线的待修复反例，不把 xfail 当 GREEN。
- `PostgresBindingDependencyAuthority.capability()` 原 SELECT 不返回持久 `source_ref`，目标测试先 exit1 `assert 'source_ref' in statement`；这是独立可安全落地的证据读取前置。

## 最小实现、回归与边界

- 仅 `services/aos-api/aos_api/aip_binding_readiness_service.py` 原 Catalog SELECT 增 `source_ref` 一列；不改 readiness 判定、权限/迁移/当前库、正常返回逻辑。`services/aos-api/tests/aip/test_aip_binding_readiness_service.py` 验其持久来源原样回读，并保留上述严格 xfail。
- 三文件组相邻 `33 passed, 1 xfailed`、exit0；`py_compile`、`git diff --check` exit0。原库仍只读135，当前进程是在本源码改动前启动，新 Reader 列待下次最新栈重启加载。
- 测试夹具提供的 `capability_source_current=False` 仅演示漏检，不是正式签名 Reader。需要在下一波明确当前 Installation/Registry/签名制品/撤销、Reader 最小授权及激活事务最终重验，再消除 xfail。当前 Growth1.13/OIDC/issuer/Owner、八配置/六Binding/自然首链仍 pending；Host/worker/Provider关。
