# W5CB4 E17-r｜当前四包启动时签名复验 verification

## 本波改动

`scripts/a0v_current_preview_http.py` 在已核树 hash 后、任何数据库连接前，以当前 trust root 快照和现有 `ManifestLoader`/`ReleasePolicy.evaluate` 逐包复验 `builder.ALL_CASES` 四个签名，并与 Receipt 四个 content hash 对齐。失败固定 `SIGNED_BUNDLE_CRYPTO_INVALID`，不会输出私钥、DSN 或包内容。E17-l 只读预检及 API 内嵌 Host 门调用同一预检。Host/worker 启动条件未放宽，当前实例仍关闭。

## 现场命令与结果

| 项目 | 命令/结果 |
| --- | --- |
| RED | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py -k matching_tree_hash`：退出 1；旧代码在哈希匹配后进入 database bootstrap，没有拒绝无效签名。 |
| GREEN 专项 | `python -m pytest -q -o log_cli=false` 指定 `test_a0v_current_preview_http.py`、`test_a0v_current_runtime_host_preflight.py`、`test_sign_ecommerce_current_candidates.py`：退出 0，17 passed。 |
| 邻接累计 | 同命令加 `test_production_runtime.py`、`test_ui_read_production_wiring.py`、`test_runtime_startup_composition.py`、`test_runtime_installations_api.py`、`test_a0v_ecommerce_runtime_host.py`：退出 0，112 passed。`git diff --check` 退出 0。 |
| 当前真实四包 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json`：退出 0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、`aos_current_preview_20260927@a0v_109`、installation approved、4 published、binding 0；只读，没有读商城源或私钥。 |
| 重算树 hash 的坏签名 | 将当前公开签名树与 trust roots 复制到临时目录，改第一包 `bundle.signature.json.signature=AAAA`，把 Receipt `signedTree` 与 `signedTreeHash` 指向临时树并重算；调用 `preflight` 退出 0（预期拒绝），输出 `SAFE_BLOCKED / SIGNED_BUNDLE_CRYPTO_INVALID / treeHashWasRecomputed=true`。原当前树未改。第一次临时试验因 macOS `/var`→`/private/var` 路径规范化被 `SIGNING_RECEIPT_DRIFT` 提前拒绝，修正为 `Path.resolve()` 后获得密码学负向。 |
| 最新代码 API | 原 PID 25092 为本任务签名预览命令，TERM 后 8080 无监听；使用同命令 `--serve` 重新拉起，日志 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`、`startup_extension_runtime_host_inactive code=DISABLED`。`curl` 8080 `/v1/health`、`/v1/ready` 与 8434 `/aip/skill-publish` 均 200；`lsof` 18181 退出 1。 |
| 权威数据卷 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg` 退出 0：running true，`aos-a0v-recovery-pg-data:/var/lib/postgresql/data`。默认 Docker context 指向 `aos-a0v-test-only`，不能用它的同名容器列表判断当前权威卷。 |

## 方案复审与待证边界

改动仅限预览启动预检和对应测试，与 E17-r 文件级方案一致。`aos_api` 包导入会构造 API app，故导入期间强制 `AOS_DOTENV_DISABLED=1` 并恢复原环境；实际当前预检只读仍有 app-created 日志。测试及手工负向证明启动时签名拒绝，不证明启动后签名树/trust roots 不漂移；已有 Registry/Host 消费期复核继续承担后续门。三身份凭据预检到连接期 TOCTOU 仍是 E17-s。正式凭据、assignment/Owner、八配置、审批/预算、首链均未齐；当前库只读、Host 关闭，不声称业务完成。浏览器指定 `browser-pilot` 当前不可用，本波无新截图。
