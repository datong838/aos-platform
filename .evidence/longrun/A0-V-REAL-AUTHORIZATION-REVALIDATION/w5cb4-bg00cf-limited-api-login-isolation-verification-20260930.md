# W5CB4 BG00cf｜受限 API 登录隔离兼容与 Event 来源边界

## 基线/隔离身份

AOS-000934、代码 m1 `eaf4459a`、当前卷 `aos-a0v-recovery-pg-data`、DB `aos_current_preview_20260927@a0v_117` 只读；8080/8434运行，18181与Host/worker/Provider关闭。BG00ce 独立 PG16 全库恢复容器 `aos-bg00ce-isolated-pg` 在 `colima-aos-a0v-test-only` 启动后，于该**独立 cluster**新建 `aos_bg00cf_api_testonly`：LOGIN、NOINHERIT、非超级用户、无 BYPASSRLS，仅成员 `aos_runtime` 且只授克隆库 CONNECT。随机 test-only 密码/pgpass 保存在离仓 `/Users/ddt/work/projects/ai_agent/.aos-testonly-bg00cf-3r_lw6yp` 0700目录内0600文件；进程环境仅有 `PGPASSFILE` 路径、无密码 `AOS_DATABASE_URL`，未向参数/环境值/日志/仓库输出密码。

## 实测路径与判据

| 路径 | 输出/退出 | 解释 |
| --- | --- | --- |
| 直接登录 test-only 身份读 `aip_action_proposal` 或 `SET LOCAL ROLE aos_app` | SQLSTATE `42501`/`42501` | 普通连接不拥有表权限，也不能冒充 owner |
| `db.connect_read_only(TenantScope('org-org','dev-project'))` | session_user=test-only login、current_user=`aos_runtime`；Proposal0、安装1 | 现有精确租户读路径可用 |
| `db.connect_read_only(platform_role=True)` | `aos_runtime`；固定 `aip_activate_network_policy` 元数据1 | 现有平台只读路径可用 |
| 现有 `AipActionStore.list_proposals`、`PostgresInstallationStore.list_installations` | 正租户Proposal0/安装1，`dev-org`安装0；退出0 | 两类当前服务代码的只读路径及 canary 读隔离正向 |
| `a0v_current_preview_http.FLAGS` 全关 worker/Host，test-only 凭据下 FastAPI `TestClient` 生命周期及 `/openapi.json` | `LIFESPAN_GREEN`, HTTP200 | 受限身份具备当前 API 启动的初步兼容性；未提供正式 OIDC 业务路由验收 |
| 独立 PG catalog | Proposal/Event owner `aos_app`、`aos_runtime` INSERT/UPDATE均true、两表非系统 trigger均0；Proposal `action_type_id` UPDATE=true | 收紧 API 登录不能单独证明网络批准 Event 真实签发 |

第一次 Store 探针在连接进入事务后尝试设置 read_only 得 psycopg ProgrammingError；改用现有 `connect_read_only` 后可行。第二次结果读取错用位置索引遇 dict_row KeyError，修正探针索引后退出0；均是隔离探针问题，无当前实例改动。测试 role 仅在独立 cluster；实测结束该容器已停止，卷/容器保留。当前真实库再读仍a0v117、正式网络 Proposal0，当前 API/Web 未重启或切换。

## 信任边界与下一施工

OIDC `require_principal`/`decide_network_activation` 仅保护应用入口，`AipActionStore.decide` 使用普通 runtime 连接写 ApprovalEvent。受限 API 登录可 `SET ROLE aos_runtime`，且普通 runtime 可写 Event 与改 Proposal action type；不能只加会话可自设 GUC、应用布尔值或“Event形状正确”放行。`aos_app` 超级用户继续运行时也不能宣称任何新数据库触发器已构成完整签发边界。

BG00cg 先文件级方案、RED/最小代码，把 `a0v_current_preview_http.py` 的服务连接改为强校验的独立 NOINHERIT API 登录和私有 pgpass，环境只传路径与无密钥连接串；签名/安装预检可由仅启动器持有的 owner 连接只读完成，但服务连接不得持有 owner密码。test-only 覆盖启动、当前安装/Action读、登录直读/冒充owner负例、非授权路径、租户隔离；正式当前身份创建/切换再独立备份、克隆、零执行窗口。完成 API 收紧后，BG00ch 为固定网络 Event 设计独立发行 login（普通 API 登录不可成为其成员）、基于不可伪造 `session_user` 的网络 Event INSERT门、Event UPDATE/DELETE和 Proposal核心字段不可变门，保留通用 Action，正式 OIDC入口用独立连接执行同事务 Store 决定；先隔离正负/撤销/到期，再另波安全迁移。a0v116 active触发器保持关闭，第二真实 checker/八配置/自然首链未通过。
