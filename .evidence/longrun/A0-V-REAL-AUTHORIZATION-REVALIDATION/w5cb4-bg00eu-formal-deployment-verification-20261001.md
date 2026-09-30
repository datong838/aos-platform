# BG00EU 正式部署与产品接线只读证据（2026-10-01）

基线 m1@74ba11ac/AOS-001009；只读盘点，无业务代码/实例变更。

## 当前实例

| 核验 | 命令/来源 | 输出与边界 |
|---|---|---|
| 当前库 | docker --context colima-aos-extension exec aos-a0v-recovery-pg psql -X -v ON_ERROR_STOP=1 -U aos_app -d aos_current_preview_20260927；BEGIN READ ONLY; SELECT current_database(),version_num FROM alembic_version; COMMIT | aos_current_preview_20260927 / a0v_118，exit0；代码119–122尚未部署 |
| 当前卷 | docker inspect同容器 --format '{{range .Mounts}}{{.Name}} {{.Destination}}{{println}}{{end}}' | aos-a0v-recovery-pg-data → /var/lib/postgresql/data；exit0 |
| 角色 | READ ONLY pg_roles精确查询issuer/consumer owner/caller | 仅issuer，canlogin/super/inherit均false；两个consumer角色无行；exit0 |
| HBA | READ ONLY SELECT DISTINCT type,auth_method FROM pg_hba_file_rules | local trust、host trust、host scram-sha-256；不是已证明SCRAM-only；exit0 |
| 栖月汇网络行数 | READ ONLY精确org-org/dev-project，Proposal action_type_id LIKE '%network%'；Event按proposal_id/双租户join；Receipt表tenant过滤 | Proposal0/Event0/Receipt0；最终exit0。首次Event探针误写p.id，SQL报column不存在，事务退出未写入；按information_schema列名回读修正后完成 |
| 监听与进程 | lsof -nP -iTCP:8080 -iTCP:8434 -iTCP:18181 -sTCP:LISTEN；ps -p 65249 -o pid=,ppid=,uid=,gid=,comm= | 8080 PID65249 ddt UID501/GID20，PPID1；8434 PID59876 ddt；18181无监听；不以端口推断首链 |

## 身份与来源边界
根.env、services/aos-api/.env、执行器环境：issuer(s)、JWKS URL(s)、audience、AUTH_ALLOW_DEV、AUTH_EXTERNAL_ONLY均unset；services/aos-api/.env不存在。仅输出存在性，不输出凭据。未读取当前运行进程完整环境，因此不声称覆盖所有配置注入来源。
根.env AOS_BUNDLE_ROOT=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-state/signed-bundles，路径存在；存在不等于签名/当前Receipt/安装来源通过，本波未做签名全链核验。
pwd.getpwall 名称含aos账号无；不是穷尽所有可能命名的独立账号。~/Library/LaunchAgents中有API/Web/Watchdog等既有文件，/Library/LaunchDaemons无aos命名项。comm进程名扫描无issuer/consumer匹配，但comm不含模块参数，不能据此宣称全机无相关进程。没有确定正式issuer/consumer进程及私有配置路径，OS/扩展ACL正向验收仍缺证。

## 启动配置异常
~/Library/LaunchAgents/com.aos.a0v-api-8080.plist 实际JSON数组（8个字符串，含uvicorn、aos_api.main:app、--host、--port），不是plist字典。Python plistlib InvalidFileException；plutil -lint报Unexpected character [。后续以JSON仅回读shape确认，未输出参数值。launchctl print gui/501/com.aos.a0v-api-8080退出113，未登记此job。
python3 scripts/a0v_real_profile_preflight.py 返回 {verdict:STOP,inspection_error:true,authorizes_profile_start:false}，exit2。此为独立真实实例恢复缺口；未修改启动文件或当前PID，未判定文件损坏原因。ensure-api.sh存在非launchd分支，所以不把文件异常等同当前API已经不可用。

## 产品接线
- routers/aip_runtime_guard_policies.py 的 decision 路由直接调用 decide_network_activation，未传connect_factory；producer明确抛 NETWORK_ISSUER_SERVICE_REQUIRED。
- apps/web/src/pages/s2/RuntimeNetworkPolicyPreviewPanel.tsx 仅只读预览，文本明确不能发布/激活。
- rg检索services/aos-api/aos_api、apps/web/src、scripts中的consume_network_once/inquire_network/aip_network_consumer_cli，除服务与IPC本身未找到API产品客户端调用；deploy/scripts/demo中未找到network consumer部署接线。
- 初次搜索误用不存在apps/web/src/pages/aip，已改为全apps/web/src；不把错误搜索当缺席证据。

## 结论/下一步
当前实例正式授权不足，继续禁入；并非长程目标无安全研发项。BG00EV计划补API侧私有IPC客户端：精确server peer、限帧/时限、一次发送、未知结果不重发、独立只读查询；先复用issuer传输军规，先方案后编码，不立即启真实服务。API启动载体异常单列恢复波，需恢复入口与备份/克隆/零窗口先齐，禁止无证据重启或替换。
本波无新增逻辑，RED/累计代码回归不适用；BG00ET的74通过仅历史证据。无UI变更，不作浏览器验收。无商城源、旧Run、manual run_definition、Host/worker/Provider启动或push。
