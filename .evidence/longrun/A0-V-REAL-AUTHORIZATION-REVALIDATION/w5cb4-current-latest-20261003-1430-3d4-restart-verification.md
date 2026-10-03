# 2026-10-03 14:30 最新 m1 与原权威卷完整重启验收

在 E17-s3o-w-l `m1@3d43567a` 代码门后执行。已有当天独立全备 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump` SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，通过容器 `pg_restore -l` stdin 读得 TOC 实体 5890；未恢复/删除或改写备份。`git diff --name-only 14a16bb1..HEAD -- services/aos-api/alembic/versions` 为空，代码/库头均 `a0v_135`。

| 门 | 实测 |
|---|---|
| 权威身份 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg`：命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；库 `aos_current_preview_20260927`。原签名回执 `.../.aos-current-build-pyGkqQ/signing-receipt.json` 原预检 exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、approved 安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、publishedVersions4、runtimeBindings0。 |
| 顺序重启 | `launchctl bootout` Web/API exit0，旧监听清空；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0。重启即时 `pg_isready` exit2，待 PG ready 后再读 `aos_current_preview_20260927|a0v_135` exit0。原签名预检复跑 GREEN 后 `launchctl bootstrap` API/Web exit0；新 PID API94957/Web94959，PG StartedAt `2026-10-03T06:29:57Z`。 |
| 端口/服务 | 18435/8080/8434 LISTEN，18181 无监听；`/v1/health`、`/v1/ready` HTTP200。Web 八个 `/workshop/*` 路由均 HTTP200；Vite 路由200仅证明可访问，不证明业务可用。新 API 日志 `migrationMode=disabled,runtimeHost=0,workersEnabled=0` 与 `startup_extension_runtime_host_inactive code=DISABLED`。 |
| 浏览器/只读业务状态 | Codex in-app browser 用户现有 `/aip/skill-publish` 重新加载，AX 与截图保存在本轮工具证据：`org-org/dev-project`，37 条仅已评测、已发布0；三缺口为正式技能放行/发布事件、当前 Logic 发布版、当前模型路由与策略，`发布此修订` disabled；侧栏“暂无可见工作台入口”。用当前签名预检解析出的连接只读调用原 `RuntimeConfigurationCandidateReader`：八类候选均0；PG `BEGIN TRANSACTION READ ONLY` 回读 Plan head/runtime binding/Host assignment 为 `0|0|0`。 |

首次直接运行候选读者未加载当前 DSN，查到默认库缺表并 exit1；改为由签名预检取得当前库精确连接，原读者 exit0 且八类0。首次尝试从容器 `/backup` 直接读当天 dump 找不到路径、主机 `pg_restore` 不在 PATH；改用容器 `pg_restore -l` stdin 成功。上述失败未改真实库。没有读商城源、重发旧 Run、手工 run_definition、启 Host/worker/Provider 或 push。完整重启是质量门，不把页面200或测试当首链完成；正式 OIDC、ToolBinding issuer/Receipt、Growth1.13 当前发布、六 Binding、八配置和自然首链仍待当前证据。
