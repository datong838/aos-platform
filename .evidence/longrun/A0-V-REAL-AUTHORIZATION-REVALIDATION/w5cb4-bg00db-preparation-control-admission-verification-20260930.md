# W5CB4 BG00db｜准备态控制命令受理门验证

## 方案一致性与最小改动

按 231-3/E16/E17 与本波文件级方案，准备态 ACTIVE Host 对 `configure/enable/disable` 在调用控制服务前固定 503 `RUNTIME_PREPARATION_ONLY`；apply/verify 原 E16 准入逻辑不变，完整模式历史行为不变。签名 Host 只读预检的准备态分支额外要求当前租户 enabled binding 数量为 0；有行或读数不可信时 `ACTIVE_BINDING_REQUIRES_FULL_HOST`。这避免准备态不装 disable/rehydrate 消费者时遗留已启用绑定。

## 命令与结果

- RED：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --disable-warnings services/aos-api/tests/extension_runtime/{test_a0v_current_runtime_host_preflight.py,test_runtime_installations_api.py} -k 'preparation_only_rejects_existing_enabled_binding or preparation_only_host_rejects_nonpreparation_controls'` → exit 1，2 failed：预检未拒绝现存启用绑定；configure 返回 202。
- GREEN 专项：相同两个测试文件完整执行 → exit 0，39 passed。
- 相邻累计：上述两文件及 `test_live_installation_owner.py`、`test_pending_preparation_directory.py`、`test_production_runtime.py`、`test_runtime_startup_composition.py`、`test_configuration_service.py`、`test_runtime_host.py` → exit 0，139 passed。
- `py_compile` 两个修改源码和 `git diff --check` 均 exit 0。当前签名准备态预检仍 exit 2，`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。
- BG00da 当前库只读已证 `aos_current_preview_20260927/a0v_118`、Host identity/assignment/operation/binding 0；本波无当前库写、无 Host/worker 启动、无未知效果重发。browser-pilot 不可用，不记浏览器验收。

## 未完成与下波

当前正式三身份凭据、Host identity/assignment/Owner 未齐，首链仍 pending。准备态切到完整模式须以当前正式候选、配置和授权链为依据；已接受旧操作只读对账，不重发。下一波只读审计正式凭据/assignment/Owner 的合法来源及候选配置缺口，在外部 authority 未齐时继续独立产品/代码项。
