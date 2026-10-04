# 2026-10-04 10:08 最新 m1 栈独立重启验收

这是 b37 代码后独立质量门，不抵扣之后送达的 `aos` 每次提醒。

| 检查 | 命令与可复核结果 |
| --- | --- |
| 写者、迁移、卷 | `git branch --show-current`=`m1`、HEAD=`b2aa9f95`；`services/aos-api/.venv/bin/alembic -c services/aos-api/alembic.ini heads`=`a0v_135`，退出0；`docker --context colima-aos-extension inspect aos-a0v-recovery-pg --format '{{json .Mounts}}'` 仍是 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`，退出0。既存 browser plugin/pnpm 与 test-only 未跟踪项保留。 |
| 备份、签名、原库 | 独立 b25 full dump 4,228,768 bytes，`shasum -a 256`=`5614c2e76d4bc4abb3229461d44abb4ffa51749ddfc06f5b5f01ff29dfbbccbc`；此前完整恢复克隆/有效权限/RLS证据沿用，不伪称本次重做。项目 venv 执行 `scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 退出0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、当前库135、4 published、approved、runtime Binding0。裸 `python3` 是系统3.9，第一次预检因不支持 `datetime.UTC` 退出1；改项目 venv 后通过。 |
| 顺序重启 | `launchctl bootout gui/501` 精确 API/Web 两 plist 各退出0；8080/8434 `lsof` 退出1、无监听符合预期。`docker --context colima-aos-extension restart aos-a0v-recovery-pg`、`pg_isready` 退出0；重跑签名预检 GREEN 后 API→Web `launchctl bootstrap gui/501` 各退出0。新 PID API80244、Web80266。 |
| 端口、健康、路由 | 18435、8080、8434 监听，18181 无监听；组合 `lsof` 退出1是18181预期缺席。`curl` `/v1/health`、`/v1/ready`、八 `/workshop/{cockpit,content-campaign,operations,creator-growth,media-studio,analyst,price-governance,customer}` 与 `/aip/skill-publish` 全部200、组合退出0。 |
| 浏览器 | CUA 原 IAB tab2 逐页读取，含加载完成复读：八工作台 8/8 均显示“当前工作台入口不可用”和“暂无可见工作台入口”。技能页 37 条仅已评测、已发布0，缺正式发布决定/事件、当前 Logic 发布版本、当前模型路由/策略三项，发布按钮 disabled；已还原技能页并保留 tab。CUA 视觉输出留在本任务，未另存仓库截图文件。 |
| 重启后原库只读 | 项目 venv 用当前签名预检连接，`SET TRANSACTION ... READ ONLY` 查到 `aos_current_preview_20260927@a0v_135`、Installation approved3/active NULL、CapabilityBinding0、runtime Binding0、Host assignment0、`dev-org/dev-project` RegistryReceipt0，退出0。直接用不存在的 `postgres` DB role 与一次错表名只读查询分别退出2/1，均未写入；正确预检身份/表名重查退出0。 |

当前 b36/b37 只读证据代码已由新 API 进程加载；并无 active 签名安装、正式受限身份或配置，所以禁入是正确结果。Host/worker/Provider未启，未读商城源、未重放旧12 Run、未手工 Run、未碰230 L0；最新栈健康不等于自然首链通过。
