# 2026-09-28 09:00 每日最新栈重启检查（实测 09:06–09:16 北京时间）

## 边界与前置

- m1 唯一写者；重启前 HEAD `c7bdb2fa`，ahead 2375，不 push。工作树原有 `test_ecommerce_content_review_pending_pg.py` 与两份 w5c8i test-only 文件，未触碰、未纳入本检查提交。
- 当前 PG 容器 `aos-a0v-recovery-pg` 精确挂载命名卷 `aos-a0v-recovery-pg-data` 到 `/var/lib/postgresql/data`；当前库 `aos_current_preview_20260927`，PostgreSQL 16.14。只读查询迁移 `a0v_109`，与 m1 最高 A0V 迁移 `a0v_109` 一致；不自动跑迁移。
- 重启前独立备份 `/Users/ddt/work/projects/ai_agent/.aos-daily-backup-20260928-zQG9WJ/aos_current_preview_20260927_a0v109_0900.dump`，权限 0600，3,893,669 字节，SHA-256 `65615f6499196b19d64769b2e092871d4d455b66fa904a90b11137f1c362c24a`。`pg_restore -l` 可读且列出 5499 TOC 项，归档记录当前库/PostgreSQL 16.14；**未做全库独立恢复演练**，不扩大声称。旧 E13 备份保留，未删除。
- 当前签名回执 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 为 `SIGNED_TREE_GREEN`，`signedTreeHash=sha256:b6aa0dbd0c9d720a8167349d90a9dfbc48b3c689aa4a1746a654aeaa9e0d144d`、trust root revision `sha256:0a99db8bcb5a2b7ff44ba974c29525cc83b5ad92acd268bf0179add93ab95752`；它是构建证据，不等于当前 Runtime Host 可执行。当前 `.env` 的 `AOS_BUNDLE_ROOT` 仍指向已不存在旧目录，列 E16 正式启动前置缺口；不以旧目录或未验证路径启动 Host。

## 重启与读回

1. 停止当前 API，确认 8080 退出；重启原 `aos-a0v-recovery-pg` 容器，不换卷；用最新 m1 的 `scripts/a0v_current_preview_http.py --signed-receipt ... --serve` 启动 API，明确 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`；随后重启 8434 Web launchd 服务。没有开启 18181、Cron、Snapshot worker 或运行 Host。
2. 8080 `/v1/health={"status":"ok"}`、`/v1/ready={"status":"ready"}`；8434 `/apollo/assets` HTTP 200；18181 无监听。只读 DB：`org-org/dev-project` 安装 1、运行 operation0、binding0、Host assignment0；`dev-org/dev-project` 安装0。此计数不是完整租户隔离证明。
3. 浏览器真实 `/apollo/assets`：Registry 显示当前四个包；唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 为 approved、revision/ETag 3/3、active 无、事件3；通用 `执行 Apply` 已禁用；运行状态 `not_prepared`、无绑定。运行面板仍露出 `准备运行资源` 可点击，但 Host/Owner 为0，故**未点击**，列 E16 核心禁入缺口。
4. 浏览器工作台目录为“暂无可见工作台入口”，八工作台真实页面/核心交互尚无法验收；电商业务登记显示“登记服务暂不可用”，只读刷新后仍相同。配置候选八类均缺少当前候选，已登记配置为空。不能把这些记为通过或宣称首链就绪。
5. 新鲜专项：后端 `test_runtime_installations_api.py` 23 passed；前端 runtime parser + panel 15 passed。测试仅证明受测逻辑，不替代独立 Host 身份、真实签名加载、八页或首链验收。一次 `pnpm --dir ... exec` 因 shell Node 不在 PATH 失败且机械改动 lockfile；已用 `apply_patch` 恢复该次自身改动，改用指定 Node 直接执行 Vitest 成功，工作树恢复原有三项差异。

## 结论与继续

每日**最新栈重启检查为基础设施可用、业务准入仍 RED**。不读商城源、不删除库/卷/备份、不重放旧 12 Run、不手工 `run_definition`、未知效果不重发。立即续行 E16 `c7bdb2fa`：先让 Host/assignment 不就绪时运行命令在页面与服务端 fail closed，并保持原幂等 Receipt 可对账；再推进当前独立身份/签名/OCI 正式准入。无需等待下一次定时任务。
