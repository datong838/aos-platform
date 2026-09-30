# W5CB4 BG00cz｜当前 Host 准入顺序核验

- 基线 `m1@45addeb0`、`AOS-000955`，任务 Receipt `W5CB4-BG00CZ-20260930`。231-3/E16/E17 文件级审计见同名 plan。
- 当前签名 Host 预检命令 `AOS_DOTENV_DISABLED=1 services/aos-api/.venv/bin/python scripts/a0v_current_runtime_host_preflight.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json`：退出 2，`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。未读、复制或构造旧凭据。
- 当前库只读 `psycopg` 查询退出 0：`aos_current_preview_20260927`，Host identity 0，`org-org/dev-project` assignment/operation/binding/configuration 各 0。BG00cy 已核批准安装修订 3、active 指针空；当前签名模板 resolver 返回 false。
- 代码精确顺序：`routers/bundle_runtime_installations.py` 的 `runtime-apply` 要求 API 同进程 ACTIVE Host 和 assignment；`main.py` 仅在 `build_production_runtime_host_selection` 为 ACTIVE 后启动 Host；该入口调用 E17-l 预检，`require_current_host_and_candidates` 在身份/assignment 后仍强制八类候选全有，否则 `CONFIGURATION_CANDIDATES_MISSING`。当前正式签名职责模板 resolver 只认 active 安装；因此**当前签名模板这一来源路径**无法先满足 Host 的八候选门再做 runtime-verify。231-3 自身允许先 verify 后配置，顺序环来自 E17 启动预检与 API 同进程要求的组合。
- 独立 Host CLI 的 `FORMAL_OWNER_AUTHORITY_UNPROVEN` 仍固定拒绝，且其 Host 状态不填 API `app.state`；解除它不能解决 HTTP 受理环。`LiveInstallationLifecycleOwner` 是操作后构造的进程对象，不能作为启动前人工凭据。
- 本波仅审计，没有改代码、运行 Host/worker、写当前库、读商城源或重放旧 Run。下波先方案/RED 实现显式准备态 Host；正式身份/assignment 缺失时当前实例继续禁入，八候选/第二 checker/自然首链仍未证明。
