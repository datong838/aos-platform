# W5CB4 BG00cb｜网络批准事件签发来源与数据库身份只读验证

## 当前基线（2026-09-30 北京时间）

- m1 `49d0e4ff`、AOS-000929；`memory-status --json` 起初 Prime 三项 STALE，执行 `memory-sync --apply --prime --json` 后强一致投影全 CURRENT，`memory-validate --json` GREEN。未编辑 01/06 自动投影。
- `docker --context colima-aos-extension inspect ... aos-a0v-recovery-pg` 返回运行中且挂载 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`。只读 PG 查询当前 DB `aos_current_preview_20260927`、迁移 `a0v_117`；签名制品 `scripts/a0v_current_preview_http.py --signed-receipt ...` preflight 输出 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、批准安装1、发布版本4、运行绑定0。
- `curl` 的 `/openapi.json`、Web `/aip/skill-publish` 均200；18181 无 LISTEN。此处只有 HTTP 可达证据，本波没有 browser-pilot 截图、页面交互或首链验收。

## 签发来源与权限

| 证据 | 只读结果 | 结论 |
| --- | --- | --- |
| `auth.resolve_principal`、`decide_network_activation`、`AipActionStore.decide` | API 验 JWT 后设置 `token_kind=oidc`；专用网络决定入口要求 OIDC，Store 复核 checker/提案并 INSERT Event；Event 无签发证明字段 | 合法应用调用链有检查，但持久 Event 本身不能证明经过此链 |
| `a0v_current_preview_http.py` | `preflight()` 从恢复容器读取数据库参数，`--serve` 将其写入 `AOS_DATABASE_URL` | 当前 8080 服务连接使用容器 `POSTGRES_USER` 登录 |
| 当前 PG 只读 `pg_roles`、`pg_class`、`pg_auth_members` | 容器登录 `aos_app` 为 LOGIN、SUPERUSER、BYPASSRLS；Event 表 owner=`aos_app`；`aos_a0v_runtime_20260912` 为 NOINHERIT/非超级用户且属于 `aos_runtime` | 当前预览 API 使用 owner/superuser；运行角色存在但未用作此 API 登录 |
| 当前 PG `has_table_privilege`、`pg_trigger` | `aos_runtime` 对 Event 表 INSERT=true、UPDATE=true；非系统 trigger=0 | 仅检查 `current_user` 或应用普通 GUC 不能构成不可伪造的网络批准来源门 |
| 当前正租户 SQL | `aip_activate_network_policy` Proposal=0、关联 ApprovalEvent=0 | 无正式网络批准可消费；不得据预检放开 active |
| `a0v_116_network_active_insert_gate.py` | active NetworkPolicy 的 BEFORE INSERT 触发器无条件拒绝 | 现行 DB 禁入仍在；本波未迁移或解除 |

## 方案一致性、风险及下波

231-5 要求正式人类审批、撤销/期限/安装依赖执行前复核；41 要求 NetworkPolicy/Egress exact 绑定。BG00ca 仅预检数据一致性，不能弥合 Event 签发缺口。当前 API owner 登录与运行角色 Event 直写是两条独立旁路；一条仅依赖应用判定的“合法签名”或任意可设 GUC 都不满足正式来源证明。本波因此保持固定网络 active DB 禁入，未改代码/当前数据库/运行开关，也没有造第二 checker。

BG00cc 先在 test-only 克隆验证 `aos_a0v_runtime_20260912` 最小权限连接是否覆盖当前预览 API 所需只读/既有通用 Action 路径，列出精确缺权而不扩大表通用授予；再设计与 OIDC 路由绑定、仅固定网络 ActionType 使用的受控签发角色/事务边界及撤销规则，RED→最小代码与隔离回归。不能安全证明来源时继续保持网络批准和 active 禁入，可并行推进独立配置来源。当前真实库任何迁移/登录切换另波需一致备份、第二全库克隆、零执行窗口；无第二正式 checker/八类配置/自然首链。
