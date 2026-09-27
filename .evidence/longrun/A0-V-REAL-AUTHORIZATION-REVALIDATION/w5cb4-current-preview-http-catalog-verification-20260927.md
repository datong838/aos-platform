# W5CB4 当前新库安全 HTTP 与浏览器目录核验（2026-09-27）

## 达到的结果

- 按 `w5cb4-current-preview-http-catalog-plan-20260927.md`，先只读确认新库 `aos_current_preview_20260927@a0v_106` 四包 published、唯一安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 为 `approved`、Runtime binding=0、签名树/Receipt exact；新脚本默认 preflight `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`。
- 只向显式 `AOS_BUNDLE_ROOT` 映射 `a0v-current` source alias，ManifestLoader、签名和 TrustRoot 校验未放松。`AOS_DOTENV_DISABLED=1`、迁移 disabled、Cron/快照/内容等 worker false、Runtime Host=0；原 8080 克隆 PID 46220 精确 TERM 后已无监听，原克隆库/备份未删。新 PID 61007 在 127.0.0.1:8080，8434 原前端 PID 1270；18181 无监听。两端健康/页面 HTTP 200；原 `aos_meta_head` 仍 `a0v_092`，新库 `a0v_106`。
- 浏览器本机页 `/workshop/cockpit` 不再报 `MANIFEST_INVALID`，而显示“当前目录没有此工作台的可见入口”；原因与 approved、Runtime binding=0 的禁入一致。`/apollo/assets` 的 Registry 标签真实显示四包；安装管理真实显示唯一安装、revision/etag 3、checker approved 决定与 3 个服务端事件。选中后运行状态为 `not_prepared`、无运行代次/绑定，并显示“运行资源尚未准备”。该页已留在浏览器给用户查看。这是 UI 的可解释禁入，不是八工作台可用。

## 测试与风险

- HTTP 脚本的签名/DB/版本/安装/binding 前置和 worker-off 专项、Bundle alias 显式配置与无配置反证：`4 passed, 7 warnings`。脚本编译、diff 检查通过；浏览器 AX 和截图实际验收。没有执行 Apply/准备运行资源/商城源/旧 Run/Provider。
- 较宽的 `test_control_wiring.py` 在当前测试环境还有 2 处失败：未来模块 import 顺序断言、假的 Connection 无 `.info`；与当前 alias 聚焦测试分开记录，未声称累计全绿。首次合并跑还受旧 `.env` 缺失目录影响；使用 `AOS_DOTENV_DISABLED=1` 和当前签名目录后该环境项消除。后续针对测试夹具/真实连接合同单独修复，不通过弱化生产权限门解决。
- 当前实例八类配置权威仍缺，下一波走正式产品配置入口和 Runtime 准备；可独立推进 P2g30b 首链返工 Action。配置未就绪前不启 Runtime Host/自然 worker、不宣称八工作台验收。
