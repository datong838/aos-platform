# 2026-09-30 09:00 北京时间｜当前卷/最新 m1 全栈重启检查

## 前置核对

- 09:01 `git branch --show-current`=`m1`，HEAD=`20118c70`；BG00cg 启动器/测试及其他用户文件仍有未提交改动，未 add；当前运行 `--serve` 路径与已提交版本的服务语义一致。`alembic heads`=`a0v_117`，当前库重启后 `alembic_version`=`a0v_117`。
- 当前 PG 容器 `aos-a0v-recovery-pg` 的挂载为命名卷 `aos-a0v-recovery-pg-data`→`/var/lib/postgresql/data`，仅本机 `127.0.0.1:18435`；目标库 `aos_current_preview_20260927`。旧独立恢复演练备份已存在；本次另作一致 custom dump 和 cluster globals，目录 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260930-daily0900-F2hDnz` 为0700，三文件0600。dump SHA256 `426594670a65390b06dfa0a9ef183e56bd117d5d5d531b6e76e24b542e3d2c14`、globals SHA256 `e79de059b92e6f589ca9ffda85083e3b18a101bc1589133eb3e969b8b6e83e7b`，`pg_restore --list` 得5615行（含头）。本日早些时 BG00ce 独立 PG16 全库恢复/控制表行摘要/密码回退演练已 GREEN；本次备份本身未重复全库恢复。
- 当前签名 Receipt `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 经 `a0v_current_preview_http.py --signed-receipt` 返回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：published4、approved安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、binding0、a0v117，签名树和信任根均匹配。

## 顺序重启与回读

1. 停 API 旧 PID29756；Web 是 launchd `com.aos.a0v-web-8434`，直接 kill 会自动再起，故 `launchctl bootout` 后 8080/8434/18181 均无监听。停服务窗口对当前库做上面备份；未删库、卷、备份，未启动 Host/worker/Provider。
2. `docker --context colima-aos-extension restart aos-a0v-recovery-pg` 退出0。立即一次 `pg_isready` 尚未就绪，等待后重试与 `SELECT version_num FROM alembic_version` 得a0v117。
3. 首次 shell `nohup` API 进程曾监听后随 shell 退出；改用私有 launchd plist `com.aos.a0v-api-daily0900`。首次 plist 未含 Docker CLI 路径，日志 `SAFE_BLOCKED FileNotFoundError`，补 `PATH` 后启动，PID44980/8080 LISTEN；未回退其他数据库或关闭安全门。Web `launchctl bootstrap` 后 PID44784/8434 LISTEN。
4. `curl` `/openapi.json`=200，`/aip/skill-publish`=200；八工作台 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 全为HTTP200。此为路由可达，未做浏览器交互/截图，不等于业务可用。`/health`=404，是该路由不存在，使用 OpenAPI/启动日志验收。18181无监听，启动日志 `startup_extension_runtime_host_inactive code=DISABLED` 与 worker disabled。
5. 真实库只读查询：`org-org/dev-project` 安装1、`dev-org/dev-project` 安装0、runtime binding0、Action Proposal0、ApprovalEvent0；未读商城源、未重放旧12 Run、未手工 run_definition。工作台仍无经真实身份/授权推进的首链。

## 风险与下波

当前 API 仍为 `aos_app` SUPERUSER 服务；BG00cg 受限启动路径的代码测试正在进行，正式切换必须另波备份/克隆/零执行。运行时普通身份仍可写 ApprovalEvent，第二真实 checker、八配置、自然首链缺失。浏览器专项工具当前不可用，页面交互/截图未验；前端HTTP200不代替该项。继续 BG00cg 方案/RED/最小实现与隔离验证，随后 Event 发行身份与数据库不可伪造门。
