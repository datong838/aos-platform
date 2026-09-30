# W5CB4 BG00EE｜active NetworkPolicy 原子消费设计核验

复习 231-4/231-5、BG00bz/ca/cb/cj～cw 后，按本波文件级 plan 只读检查 `aos-bg00dl-isolated-pg`；当前真库未写。m1 基线 `f14d39e7`，权威 `AOS-000992`。

| 命令/来源 | 退出码与事实 |
| --- | --- |
| `docker exec aos-bg00dl-isolated-pg psql -U aos_app -d postgres -Atc "SELECT datname ..."` | 0；克隆 DB 名 `aos_current_preview_20260927`。 |
| 克隆 `alembic_version`、`pg_roles`、`pg_trigger`、`pg_class` 只读查询 | 0；a0v_118；`aos_app` LOGIN/SUPERUSER/BYPASSRLS 且是 NetworkPolicy revision 表 owner；`aos_runtime` 与 `aos_network_approval_issuer` NOLOGIN；active insert guard、append-only trigger 均启用。 |
| `pg_indexes` 只读查询 | 0；Receipt 唯一键 `(org_id,project_id,operation,idempotency_key)`，消费必须固定 `idempotency_key=proposal_id` 并重核 request hash。 |
| `aip_network_policy_approval_consumer.py` 与 BG00ca 测试 | 0；现有 `precheck_network_activation` 只读、锁 Proposal/Approval，明确不消费、不允许 active INSERT。 |
| BG00ED 专项 | 1；旧测试直插 active 网络行被 a0v_116 拒绝。此 RED 是真实缺口，不得通过禁用门消除。 |

设计复审结论：已存在签发者身份隔离与只读预检，但 DB 消费门尚无安全实现。当前 app 使用 `aos_app` owner/superuser 的历史路径；若新 SECURITY DEFINER 函数也由其拥有且宽授 API，不能证明批准者、调用者与消费者不可互冒。因此本波未开码迁移/消费函数；先要求专用非特权函数 owner、独立 issuer 和窄调用登录角色的权限矩阵及克隆 RED/正向，不能拿当前单 owner 伪造 checker。当前库不迁移、Host/worker/Provider 仍关闭，首链 pending。

下波 BG00EF 从可独立完成的产品配置入口继续：复查八候选当前页面和 RuntimePolicy 精确依赖提示，挑最小可复现缺口，方案→RED→最小修复→专项/累计；网络消费安全设计作为明确并行门，不以页面可点冒充正式配置。无商城源读、dev-org 写、旧 Run 重放、手工 run_definition 或 push。
