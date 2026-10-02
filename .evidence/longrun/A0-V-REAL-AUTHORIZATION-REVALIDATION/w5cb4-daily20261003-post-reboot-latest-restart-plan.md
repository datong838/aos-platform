# 2026-10-03 重启后最新 m1/当前权威卷完整验收方案

## 固定目标与安全边界

- 当前 `m1@93a6e4f7`，Alembic 唯一头 `a0v_135`，当前权威 `colima-aos-extension/aos-a0v-recovery-pg` 命名卷 `aos-a0v-recovery-pg-data`、库 `aos_current_preview_20260927@a0v_135`。本次无迁移或切库；当前真实库继续只读，不删除任何库/卷/备份。
- 只重启当前禁入预览栈 PG→API→Web。正式受限 API 因外部 OIDC/独立身份未齐另列；Host/worker/Provider与18181保持关闭，不读商城源、不重放旧12 Run、不手工 run_definition、不 push。
- 两个 LaunchAgent 为 `com.aos.a0v-api-daily0900`、`com.aos.a0v-web-8434`；API 启动器为当前 m1 的 `scripts/a0v_current_preview_http.py --signed-receipt ... --serve`，Web 工作目录当前 m1 `apps/web`。先只读签名预检，确认身份/安装与备份。

## 有界次序与恢复

1. 复核单写/HEAD/工作树、代码和库均135、安装/签名 Receipt；创建本日独立一致 `pg_dump -Fc` 并做 SHA/TOC 校验，保留昨日已全库恢复演练备份。任一不符停止本次切换，继续安全研发而不伪称最新。
2. 精确 bootout Web、API，确认8080/8434/18181无监听；仅重启原 `aos-a0v-recovery-pg` 容器/原卷，等 `pg_isready`，再只读回版本/安装/签名。
3. bootstrap API、Web 原 LaunchAgent；回读新 PID/启动时刻、端口18435/8080/8434、18181关闭、健康/ready/OpenAPI、八工作台与 AIP 页面。浏览器检查禁入/业务入口，当前库只读核安装/租户/八候选/Host assignment/binding。
4. 记录所有命令退出码与失败。API/Web 如不能启动，按原 plist/同一卷恢复禁入预览，不开启 Host 或越权切换。

## 验收定义

页面200仅说明可达；必须逐项回读当前数据库、签名安装、候选与禁入交互。即使本次 GREEN，也不将预览栈说成正式受限身份或自然首链。
