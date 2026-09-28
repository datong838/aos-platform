# W5CB4 E17 当前运行准入接续审计（2026-09-28 11:15–11:23）

## 范围与结论

本波只恢复当日最新 `m1@14a54efb` 的安全预览栈、修正本机过期签名根并只读核验正式准入。E16 失败封闭专项通过；E17 正式 Host 三身份凭据、OCI 配置与精确 assignment/Owner 未齐，保持 Runtime Host/worker 关闭。没有读商城源、写当前库、重放旧 Run、手工 Run 或推送。

## 可复核记录

| 节点 | 命令或来源 | 结果 |
|---|---|---|
| 工作树 | `git status --short --branch`、`git diff -- services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` | `m1@14a54efb`；原 P2g 返工审批测试改动仍未提交；两份 w5c8i test-only 未跟踪文件未碰。该差异不属于 E17 方案，未混入本波。 |
| 记忆门 | `scripts/memory/memory-status --json`、`memory-validate --json` | 强一致投影 CURRENT；AOS-000814；validate GREEN。Task Receipt `A0V-W5CB4-E17-20260928-CONTINUATION` 已登记。 |
| 原卷重启 | `colima start --profile aos-extension`；`docker --context colima-aos-extension inspect/start aos-a0v-recovery-pg` | `aos-a0v-recovery-pg-data=>/var/lib/postgresql/data`，18435 loopback，`pg_isready` accepting；没有换卷或迁移。 |
| 签名与安装预检 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` | `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：当前库 `aos_current_preview_20260927@a0v_109`，安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved，四包 published，binding 0；脚本核签名目录存在与树哈希、Registry exact 版本/contentHash。签名构建不等于 Host 加载。 |
| API/Web | 上述脚本 `--serve`；`launchctl kickstart -k gui/$(id -u)/com.aos.a0v-web-8434`；`curl` 8080 health/ready、8434 `/apollo/assets` | 启动回执 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`；health/ready 200 `ok/ready`，Web 200；8080/8434/18435 监听，18181 无监听。 |
| 本机签名根 | 先读 `.env` 与当前签名回执，再将唯一 `AOS_BUNDLE_ROOT` 从不存在的目录更新为 receipt 中已存在的 `signedTree` | 本机 `.env` 被 `.gitignore` 排除；仅改一行，无密钥写入仓库；预览脚本仍显式选当前 receipt。没有因此开启 Host。 |
| 当前库只读 | 对当前容器连接 `BEGIN READ ONLY` 查 `alembic_version` 与 scoped 计数 | `a0v_109`；`org-org/dev-project` 安装 1、`extension_runtime_operation=0`、`extension_runtime_binding=0`、`extension_runtime_host_assignment=0`。 |
| 身份与 OCI | 只查 `.env` 配置有无、`pg_roles/pg_auth_members` 分类，不输出 DSN 或密码 | DB 中存在独立的非特权 runtime/directory/web 登录角色，分别为 runtime 组、directory 组、无两组成员；本机未配置 `AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE` 或 runtime/directory DSN，未配置 `AOS_EXTENSION_OCI_CONTEXT`，Host 开关未启。当前预览登录为 superuser/BYPASSRLS，不能当正式 Host 身份。 |
| E16 专项 | 先因测试专用 Colima 停止导致 62 个 setup error；启动 `aos-a0v-test-only/aos-a0v-test-pg` 后原样复跑三个专项文件 | `62 passed, 7 warnings`，退出码 0。隔离测试库自动创建/清理；当前权威库未用于测试。 |

## 未验证与停止门

本轮没有可用的 `browser-pilot` 可调用入口：仓库 `plugins/agents/browser-pilot` 不存在，当前工具清单无 BrowserPilot。因此没有新鲜浏览器截图，不声称 `/aip/skill-publish` 三 blocker、工作台无入口的本轮页面验收；E16 之前的浏览器记录仅作历史证据。没有通过其他浏览器引擎绕过指定工具。八类配置候选和安装 Owner 本轮亦未得到新的正向权威证明。

正式 Host 只有在受保护三身份文件或独立 DSN、OCI 固定 context、当前签名根、精确 tenant assignment/Owner 与配置候选全部有当前权威证明后才可进入有界启动；本轮条件不成立，保持 E17 pending。迁移/切换当前库须另波备份恢复演练和零执行窗口。旧 12 Run、230 L0、自然 worker/Provider 均保持挂起。
