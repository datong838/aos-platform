# 2026-10-04 09:17 最新 m1 栈独立重启验收

这是 b35 代码提交后的一次独立质量检查，**不是** `aos` 自动提醒的代偿；若该提醒随后送达，仍按其要求另执行一次。

| 检查 | 具体命令／退出码／读回 |
| --- | --- |
| 写者与代码 | `git branch --show-current`=`m1`，HEAD `86401176`；工作区 browser plugin/pnpm 既存变动及 test-only 未跟踪项均保留；`alembic -c services/aos-api/alembic.ini heads`=`a0v_135`，exit0。 |
| 卷与备份 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg` 名称卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；独立 b25 full dump 4,228,768 bytes，`shasum -a 256`=`5614c2e76d4bc4abb3229461d44abb4ffa51749ddfc06f5b5f01ff29dfbbccbc`，exit0；b25 克隆恢复/ACL/RLS 演练沿用原证据，不伪称本次重做。 |
| 当前库与签名 | `BEGIN READ ONLY` 回读 `aos_current_preview_20260927|a0v_135`、CapabilityBinding0、runtime Binding0；`a0v_current_preview_http.py --signed-receipt .../signing-receipt.json`=`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、4 published、approved 安装、0 runtime Binding，exit0。当前签名 Growth仅1.11.0。 |
| 顺序重启 | `launchctl bootout` 精确 API/Web 两 plist exit0；8080/8434 `lsof` 无监听 exit1（预期）；`docker ... restart aos-a0v-recovery-pg`、`pg_isready` exit0，回读同库135；`launchctl bootstrap` API 后 Web exit0，新 PID 77370/77396。 |
| 端口/路由 | `/v1/health` 与 `/v1/ready` 200；18435、8080、8434 监听，18181 不监听（组合 `lsof` exit1 因 18181 缺席）；八个 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 和 `/aip/skill-publish` 均 HTTP200。 |
| 浏览器 | CUA 在原 IAB tab2 逐页等待加载：八工作台均显示“当前工作台入口不可用/暂无可见工作台入口”；内容工作台首次读取尚在加载，再读取后证实禁入。技能页 37仅已评测/0发布、三项 blocker、发布按钮 disabled；还原原 `/aip/skill-publish`。CUA 当前任务视觉输出，截图未另存仓库文件。 |
| 后读租户 | `BEGIN READ ONLY`：Installation `org-org/dev-project approved3 active NULL`，CapabilityBinding0、runtime Binding0、Host assignment0、dev-org RegistryReceipt0，exit0。未读取商城源、未回放 Run、未手工 Run；Host/worker/Provider未启。 |

本次进程加载 b34 source_ref Reader 与 b35 纯重算代码。当前正式 Growth1.13/三身份、Owner、八配置/六绑定仍缺，八页禁入是正确失败封闭；重启成功不等于业务首链完成。
