# 2026-10-03 16:44 CST｜s3o-w-q 后最新栈重启验收

- 基线：`m1@433390eb`，代码/当前数据库 migration `a0v_135`。当前命名卷 `aos-a0v-recovery-pg-data` 挂 `/var/lib/postgresql/data`，数据库 `aos_current_preview_20260927`；非 test-only 当前库。
- 独立备份 `/Users/ddt/work/projects/ai_agent/aos-recovery/.aos-current-backup-20261003-post-reboot-135/current-full.dump`：SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0`，`pg_restore -l` TOC 5890。已验可列 TOC，未宣称全库恢复演练通过。
- 先停止 API/Web LaunchAgent，随后重启当前 PG。首次 `pg_isready` exit2（PG 正启动），再次检查 `accepting connections`；复跑签名预检 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved、发布版本4、runtimeBindings0，签名根与 trust roots 路径由预检逐项回读。之后启动最新代码 API/Web，PID 5804/5807；PG StartedAt `2026-10-03T08:44:03Z`。
- API `/v1/health`、`/v1/ready` 200；Web `/aip/skill-publish` 与八个 `/workshop/{overview,growth,customer,merchandise,operations,finance,fulfillment,agent}` 路由均200。监听仅 8080/8434，18181 无监听。
- IAB 浏览器实际页面：org-org/dev-project，37 条仅已评测、已发布0；所选技能缺正式放行决定/发布事件、业务逻辑发布版、可用模型路由/运行策略三阻断，发布按钮 disabled；电商工作台提示“暂无可见工作台入口”。这只证明当前安全禁入与页面可用，不证明业务首链。
- 只读 PG：八类有效配置计数均0，Host assignment0、ToolBinding0、runtime binding0、BI Plan0；受限 BI 测试角色/三个 test-only 函数/一次性测试库残留均0。Host/worker/Provider 没有开启，当前库无迁移或写入，未读取商城源、未触发 Run。
