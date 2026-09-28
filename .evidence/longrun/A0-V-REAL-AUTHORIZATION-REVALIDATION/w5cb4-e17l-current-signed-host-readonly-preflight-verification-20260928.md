# W5CB4 E17-l｜当前签名安装与三身份目标库只读交叉预检验证

## 改动与合同

- `scripts/a0v_current_runtime_host_preflight.py` 只接受显式签名 Receipt 与受保护的绝对凭据文件；先复用当前签名/安装/库预检，再拒绝旧库 DSN，实际只读连接三身份，比对同一物理库及角色隔离，精确读取 `org-org/dev-project` 的 assigned Host identity 和八类配置候选。所有失败输出固定无密钥 reasonCode。它不启动 Host，也不替代后续正式 Owner/安装生命周期授权。
- `scripts/a0v_current_preview_http.py` 的签名安装预检显式设置只读；同步测试中的当前迁移头为 `a0v_109`。不写当前库。

## 当轮命令和结果

| 检查 | 命令或路径 | 结果 |
|---|---|---|
| RED | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_a0v_current_runtime_host_preflight.py` | 新脚本未存在，8 errors；随后实现。 |
| 专项及相邻回归 | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_a0v_current_runtime_host_preflight.py services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py services/aos-api/tests/extension_runtime/test_production_runtime.py --disable-warnings` | 退出 0；52 passed，7 warnings。旧库 DSN 在任何身份连接前拒绝，签名异常在凭据读取前拒绝。 |
| 当前签名和库 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` | 退出 0；`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，`aos_current_preview_20260927@a0v_109`，安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved，4 published，binding 0。 |
| 正式身份缺口 | `services/aos-api/.venv/bin/python scripts/a0v_current_runtime_host_preflight.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` | 退出 2；`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。没有读取或复制旧凭据。 |
| Runtime Host | `lsof -nP -iTCP:18181 -sTCP:LISTEN` | 退出 1，无监听。8080 `/v1/health` 和 8434 `/aip/skill-publish` HTTP 200；仅代表服务/页面可达。 |
| 静态检查 | `services/aos-api/.venv/bin/python -m py_compile ...`、`git diff --check` | 均退出 0。 |

## 仍未证明

当前正式受保护三身份凭据、固定 OCI、精确 enabled Host identity/assignment、安装生命周期 Owner 和八项 active 配置均未齐；当前库只读，预检没有正向真实凭据试验，首链未开始。测试替身只验证失败路径和检查逻辑，不能代替当前正式授权。`browser-pilot` 当前不可用，未作新截图。下一波先让正式 Owner 合法提供当前凭据与配置，再把本只读交叉预检接在**有界** Host 启动入口前，保留独立正式授权门；缺任一项继续禁入。
