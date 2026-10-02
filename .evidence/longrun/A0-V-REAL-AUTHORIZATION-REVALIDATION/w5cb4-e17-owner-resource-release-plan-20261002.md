# E17 Owner 前置｜运行资源释放事实只读证据修正

## 上位合同与当前事实

复习 231 主计划 §A1、231-3 §3 和 E17 正式启动 Owner 方案：安装 active、同代 ready binding 与 OCI 签名只是运行候选；Host 启动与每次业务调用仍需当前配置、权限、预算、epoch/fence、资源存活和独立身份。当前实例八配置、assignment、binding、正式外部 OIDC/凭据仍缺，Host 固定禁入，当前库只读。本波不改这些准入状态。

`current_installation_release_evidence.read_current_runtime_image_evidence` 是 E17 正式 selector 的只读前置。它查询 `extension_runtime_resource_lease` 时核 `cleanup_state='pending'`、container ID 与过期时间，却未读取 `observed_release`。原 `PostgresPendingPreparationDirectory` 的 rehydrate 读者明确把 `observed_release` 当作非存活事实拒绝。若已观察到资源释放而 cleanup 状态仍 pending，现有 selector 可能仍返回 `PREFLIGHT_ONLY_NO_RUNTIME_START`，给未来 Owner 一个错误的资源候选。

## 文件级最小改动

- 代码：`services/aos-api/aos_api/extension_runtime/current_installation_release_evidence.py`，前 SHA256 `9ebb7a42a716ecf5c7b3fbfeda070fa4143a245f1ef0bf9d5adad4c51f87a622`。仅把 `observed_release` 加入同事务资源查询与 `RUNTIME_RESOURCE_NOT_LIVE` 判据。不改 selector/Host，不放行任何启动。
- 测试：`services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`，前 SHA256 `aee1081d3872a3779e5be1feadf786bf685ea5310cb0c958a8b5bac0cf256559`。在原 Registry→安装→runtime apply/verify 与 OCI 正链的隔离 PG 中，在正常证据读回之后、原 Job 停止之前，以测试库事务标记一个已观察释放的资源，RED 证明同代证据拒绝，事务回滚后正常证据仍可读。只操作可销毁测试库，不触碰当前库。

## 验证与边界

先运行单例 RED，再作一处代码修复，单例 GREEN、相邻 release/selector 与原生命周期测试；`py_compile`、`git diff --check`。无页面改动；本日浏览器八页与禁入已由完整重启证据覆盖。复审 231-3：资源释放观察不能被 pending 状态抵消；只读视图始终 `EVIDENCE_ONLY_NO_START`，Host 固定禁入。验证失败回退该两文件改动，不变更数据库/卷/备份。下一波仍是 E17 正式身份、八配置与精确 Owner，或独立原 Review producer。
