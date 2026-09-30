# W5CB4 BG00da｜显式准备态 Host 验证

## 上位方案与改动

依据 231-3、E16/E17 和本波文件级方案，只在显式 `AOS_EXTENSION_RUNTIME_PREPARATION_ONLY=1` 且当前签名/物理库/三身份/精确 Host identity 与 assignment 预检通过时选择准备态。完整模式仍要求八类配置候选。准备态只投递 pending apply/verify；目录排除 rehydrate，Owner 不构造 enable consumer，Host 无配置/UI/停用消费者，API 不启动自然业务 worker/Provider。默认完整模式保留原顺序。改动路径见本波精确 Git 提交。

## 可复核证据

- RED：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/{test_live_installation_owner.py,test_pending_preparation_directory.py,test_production_runtime.py} -k 'preparation_only_never or preparation_only_directory or preparation_only_factory or preparation_only_selector'` → exit 1，4 failed；缺 Owner/目录/工厂模式参数及选择器禁入接线。
- GREEN：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --disable-warnings services/aos-api/tests/extension_runtime/{test_live_installation_owner.py,test_pending_preparation_directory.py,test_production_runtime.py,test_a0v_current_runtime_host_preflight.py,test_runtime_startup_composition.py}` → exit 0，77 passed。
- 相邻累计：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q --disable-warnings services/aos-api/tests/extension_runtime/{test_production_preparation.py,test_preparation_consumer_pg.py,test_live_installation_scheduler.py,test_runtime_host.py,test_lifecycle_service.py}` → exit 0，60 passed/13 skipped。13 skipped 为未启用 PG 集成测试，不计正向证据。
- 当前正式只读：`scripts.a0v_current_preview_bootstrap._connection_parameters()` 建立 `conn.read_only=True` 后读 `current_database()`/`alembic_version`/四表计数 → exit 0；`aos_current_preview_20260927`、`a0v_118`，Host identity/assignment/operation/binding 均 0。
- 当前签名 Host 命令：`AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python scripts/a0v_current_runtime_host_preflight.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json --preparation-only` → exit 2，`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。
- `git diff --check` → exit 0。browser-pilot 不可用，未声称浏览器正向验收。本波未启动当前 Host/worker，也未写当前库或回放 Run。

## 复审结论与剩余门

代码门证明准备态不会执行 enable、rehydrate、配置和自然业务 worker；它不证明当前正式实例具备授权。当前三身份凭据文件、Host identity/assignment 与正式 Owner 均缺。`configure/enable` API 仍有独立安装 active、当前配置/权限门；准备态不消费其 outbox，后续需单独审查在准备态下的受理反馈与完整模式切换。下一波优先审查这个受理门及正式凭据/Owner 来源；任何当前实例正向 Host 启动须先完成正式身份和 assignment 证据。
