# W5CB4 BG00EE｜active NetworkPolicy 原子消费文件级方案

## 上位与已有事实

复习 231-4/231-5、BG00bz 消费合同、BG00ca 只读预检、BG00cb 签发来源审计、BG00cj～cw 独立 issuer 施工和 BG00ED RED。当前代码/库 a0v_118；`a0v_116` 无条件拒绝 active NetworkPolicy INSERT。当前实例只有 owner 一人，正式 checker/网络 Proposal/Event 均 0。不得把已有预检、隔离合成账号或角色拓扑测试解释成当前正式批准。

## 本波设计边界

目标是一个**专用、同事务、可审计**的消费通道：锁定当前 Proposal、唯一 approved Event、head/依赖，核 tenant、maker/checker 当前角色与分离、版本、撤回/到期、目标 hash 和 Egress，再原子写 active revision 与以 `proposal_id` 为唯一消费键的 Receipt。重复请求只读原 Receipt；漂移冲突；事务异常/未知结果先只读对账。数据库门只向该专用路径开放，普通 runtime、owner API、任意手工 SQL 继续被拒。不得以可自设 GUC、禁用 trigger、超级用户入口或假账号授权。

| 文件/对象 | 计划与先决检查 |
| --- | --- |
| `services/aos-api/alembic/versions/a0v_116_network_active_insert_gate.py` | 只读基线；不改旧迁移。新增版本须先检当前 migration head 与命名，独立隔离库演练，当前库迁移另波。 |
| `services/aos-api/aos_api/aip_network_policy_approval_consumer.py` | 复用既有只读预检；先确认它的锁/时间/DB 身份能否在正式消费事务内复用，不能仅靠预检结果放行。 |
| `services/aos-api/aos_api/aip_network_policy_store.py` | 保留普通 `publish(active)` 拒绝；另设计窄激活命令与原 Receipt 读回，不扩通用 publish 权限。 |
| 新 Alembic 版本和专用 DB 函数 | 单事务数据库可证明 Proposal/Event/Receipt 与 active 插入门；函数 owner/EXECUTE 最小授权；不能将旧 DB 门全局放开。先审安全设计再开码。 |
| `services/aos-api/tests/aip/test_aip7_model_runtime_store.py` | 旧测试直插 active 网络行已被 a0v_116 正确拒绝；待合法消费路径具备后改为专用隔离正向，不跳过整条依赖链来伪造 GREEN。 |
| 新 test-only PG 合同测试 | RED：普通 runtime 直插、假 Event、同 maker/checker、过期/撤回/漂移、跨租户、重复/UNKNOWN 均拒绝；正向仅用隔离的独立 issuer 与 checker 身份，证明一次消费及重读。 |

## 开码前精确核验

1. 检查当前数据库角色、表 owner、RLS、触发器、Receipt 唯一键与 precheck SQL；确定 SECURITY DEFINER 的实际权限及可执行 role，不假设 `current_user` 可作为人类身份。
2. 冻结函数参数和返回 Receipt、request hash、错误码、锁顺序，复核第三方 code path 不能直连函数/表绕过独立 issuer。
3. 文件级安全评审通过才写 RED 和最小代码；若关键事务门无法在 test-only PG 证明，保持 a0v_116 拒绝并转做可独立推进的配置产品入口。

当前权威卷只读；Host/worker/Provider 关闭；不读商城源、不写 dev-org、不回放旧 12 Run、不手工 run_definition、不 push；230 L0 挂起。

## 隔离克隆只读复核后修订

`aos-bg00dl-isolated-pg` 中 DB 为 `aos_current_preview_20260927@a0v_118`。`aos_app` 是 LOGIN+SUPERUSER+BYPASSRLS 且拥有 NetworkPolicy revision 表；`aos_runtime`、`aos_network_approval_issuer` 均 NOLOGIN，后者仍无正式凭据。`aip_network_active_insert_guard` 和 append-only trigger 均启用；Receipt 唯一键为 `(org_id,project_id,operation,idempotency_key)`。因此**不能**把 SECURITY DEFINER 函数简单设为现有 `aos_app` owner 并授予现有 API：这会让超级用户 owner 路径成为签发捷径。本波先冻结为安全设计待定，未写迁移或消费代码；后续必须证明专用非特权函数 owner、调用登录角色和 Event 独立 issuer 三者不可互相冒用，再进行 RED/实现。
