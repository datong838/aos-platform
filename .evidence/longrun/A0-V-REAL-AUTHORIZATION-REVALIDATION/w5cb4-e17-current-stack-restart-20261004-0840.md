# 2026-10-04 当前最新 m1 栈重启验收（08:40）

## 重启前安全门

- `git branch --show-current`=`m1`，HEAD `01ef52ca`，工作区只有既存浏览器插件/pnpm及未跟踪 test-only 现场项，未精确暂存外文件。代码 Alembic head `a0v_135`。
- `docker --context colima-aos-extension inspect aos-a0v-recovery-pg`：`aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；`BEGIN READ ONLY` 读 `aos_current_preview_20260927@a0v_135`、runtime binding0、CapabilityBinding0、Host assignment0。
- 独立完整恢复过的 b25 dump `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261004-s3owaob25-XaGvdX/current-full.dump` SHA256 `5614c2e76d4bc4abb3229461d44abb4ffa51749ddfc06f5b5f01ff29dfbbccbc`，4,228,768 bytes；b25 全库克隆恢复/effective ACL/RLS 已验证，不将本次 SHA 检查冒充重新恢复演练。
- 当前签名 Receipt 预检 exit0 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`：4 published、approved 安装、0 runtime Binding，签名根 Growth仅1.11.0。正式 Growth1.13/Owner仍缺，Host/worker/Provider保持关闭。

## 顺序重启与读回

- 精确 bootout `com.aos.a0v-api-daily0900.plist`、`com.aos.a0v-web-8434.plist`，`lsof` 对8080/8434无监听（exit1为预期）；`docker --context colima-aos-extension restart aos-a0v-recovery-pg` exit0，`pg_isready` exit0，同库/迁移读回。
- 精确 bootstrap API 再 Web：新 PID `75238`/`75282`；`/v1/health`、`/v1/ready` 均200，18435/8080/8434监听，18181无监听。八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与 `/aip/skill-publish` HTTP均200。
- CUA 浏览器逐页读八工作台：全部显示“当前工作台入口不可用/暂无可见工作台入口”；技能发布页显示 org-org/dev-project、37仅已评测、0已发布、三 blocker、发布按钮 disabled。CUA 当场截取技能页和工作台禁入画面（当前任务图像输出）；截图未写入仓库文件。浏览器恢复原 `/aip/skill-publish`。
- 后读真实库 `BEGIN READ ONLY`：`a0v_135`、Installation `org-org/dev-project:approved:3:NULL`、RegistryReceipt `org-org=6`、CapabilityBinding0、Host assignment0、runtime binding0；dev-org未产生行。无自然首链、无当前 Growth1.13 发布/运行。

本次重启加载最新工作树生产代码（含 b31 `source_revision`），但因正式发行身份缺失未执行当前实例 Capability create，不能以进程启动证明新命令正向。若每日 `aos` 提醒稍后送达，按该提醒再独立执行一次，不以此记录跳过。
