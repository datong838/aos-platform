# W5CB4 E17-m｜Host 启动入口当前签名交叉预检接线验证

## 本波实际改动

`scripts/a0v_ecommerce_runtime_host.py` 命令入口增加显式 `--signed-receipt`。持有原单例锁后，在环境配置/Host selector/任何 worker 构造前调用 E17-l 的当前签名只读预检。失败只输出固定无密钥代码；成功仍固定返回 `FORMAL_OWNER_AUTHORITY_UNPROVEN`，因为该预检只证明配置候选和 Host assignment，尚无正式安装生命周期 Owner、精确配置绑定与预算审批 Receipt。此硬门是当前诚实禁入，后续不得仅以测试值或字符串参数解除。

## 验证

| 证据 | 命令与结果 |
|---|---|
| RED | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py -k 'current_preflight or signed_receipt' --disable-warnings`：退出 1，3 failed；原入口可在缺签名 Receipt 时走到 `_serve`。 |
| GREEN | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py services/aos-api/tests/extension_runtime/test_a0v_current_runtime_host_preflight.py services/aos-api/tests/extension_runtime/test_production_runtime.py --disable-warnings`：退出 0，53 passed、7 warnings。覆缺 Receipt、预检失败、预检 GREEN 仍禁入、锁持有/释放和原内部 Host 行为。 |
| 语法与差异 | `services/aos-api/.venv/bin/python -m py_compile scripts/a0v_ecommerce_runtime_host.py scripts/a0v_current_runtime_host_preflight.py` 与 `git diff --check`：退出 0。 |
| 现场 | `lsof -nP -iTCP:18181 -sTCP:LISTEN`：退出 1，无 Host 监听；`curl http://127.0.0.1:8080/v1/health`：HTTP 200。没有启动 Host/worker、写当前库、碰旧 12 Run。 |

## 限制和下一门

这波没有正向真实凭据与正式 Owner Receipt，因此不证明 Host 可启动，也不证明自然首链。下一波核当前安装生命周期 Owner、批准/预算/配置绑定的现有 DB 合同，先只读盘点，再文件级方案与 RED，只有完整正式授权才替换 `FORMAL_OWNER_AUTHORITY_UNPROVEN`。当前 `browser-pilot` 不可用，截图待补。
