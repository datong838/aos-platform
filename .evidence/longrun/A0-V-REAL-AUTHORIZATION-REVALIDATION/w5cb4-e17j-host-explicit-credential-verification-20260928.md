# W5CB4 E17-j｜Runtime Host 显式身份文件禁入验证（2026-09-28）

## 方案/代码复核

- 按同目录文件级计划，仅改 `scripts/a0v_ecommerce_runtime_host.py` 和原 Host 测试。CLI 不再默选 `.aos-recovery-20260912` 历史身份文件；缺 `--credential-file` 在获得单实例锁、校验 interval 后、进入 `_serve` 前写 `SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED` 并退出 2。
- 显式文件的 0600/角色检查、签名根、OCI 配置、组合根三身份/数据库预检及 Host 功能逻辑未改。非法 interval 和竞争锁仍优先失败封闭；现有模拟 `_serve` 测试补显式文件参数。

## 新鲜证据

| 检查 | 结果 |
| --- | --- |
| RED | `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py -q`：退出 1，16 passed/1 failed；缺参数时旧代码确实带历史默认文件进入 `_serve`。 |
| GREEN 与相关累计 | `services/aos-api/.venv/bin/python -m pytest services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host_bootstrap.py -q`：退出 0，24 passed。 |
| 语法与差异 | `compileall -q` 两个变更文件、`git diff --check` 均退出 0。 |

## 未完成与边界

本次未执行 Host、worker、Provider 或当前库写操作；缺当前受保护三身份/固定 OCI/启用 Host identity/精确 assignment 时依然禁入。显式传旧文件仍须由既有三身份同库/安装/Owner 组合门拒绝，后续可加“当前签名安装与凭据目标同库”的前置诊断；本波不称正式 Host 可启动。浏览器 `browser-pilot` 截图仍未补。
