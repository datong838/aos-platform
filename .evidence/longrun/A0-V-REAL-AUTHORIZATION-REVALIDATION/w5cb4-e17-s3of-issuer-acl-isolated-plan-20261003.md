# E17-s3o-f｜AIP 独立发行身份与 ACL 隔离施工计划

基线 `m1@9becc509`、`AOS-001190`；上位 231-4/231-9、续接577、D-waves 和 s3oe verification 已读。当前真实库 `aos_current_preview_20260927@a0v_135` 只读；本波仅 disposable PG。方案军规：公共 Store 受信命令、Receipt-first、幂等/CAS、租户 RLS、非 owner/非 BYPASSRLS 专用角色；不得给领域包任意 SQL/凭证。

## 原路径和兼容约束

| 文件 | 合法写路径 | 身份现状/施工注意 |
|---|---|---|
| `aip_agent_registry_store.py` | create/update AgentInstance 与同事务 `aip_agent_registry_receipt`；模板发布为平台命令 | `db.connect(scope)` 将受限登录切成 `aos_runtime`；单独撤 Receipt INSERT 会使原命令失败。|
| `aip_skill_registry.py`、`aip_capability_binding_service.py` | Skill/Capability Binding create/update/evaluate 与同事务 Registry Receipt | 必须保持单事务和幂等键；不能靠应用传的 actor 字符串当 DB issuer。|
| `aip_assignee_resolution_store.py` | `upsert_tool_binding`、`resolve` 写 Assignee Receipt | `/v1/aip/assignee-authority` 对 admin/executor/aip_executor 做 HTTP 角色判断，DB 仍是普通 `aos_runtime`；需精确保护 Tool/Receipt 写。|
| `db.py`/`tenant_scope.py` | `SET LOCAL ROLE aos_runtime` + org/project GUC | 为正式 issuer 分离连接/角色时不得失去原 TenantScope、RLS 与事务局部性。|
| `228ti2e6_module_rls.py`、`aip6_001`、`aip6_002`、`aip13_001` | 历史迁移广授/新增表窄 GRANT | default ACL `arwd` 仍使五表 SIUD；新迁移必须显式 REVOKE 现存授权，不能只追加 GRANT。|

## RED、最小修复与验收顺序

1. 在 disposable PG 用非 superuser `aos_runtime` 与 `org-org/dev-project` GUC，证明至少 Registry/Assignee Receipt 直接 INSERT 能越过当前 ACL（事务最后 ROLLBACK）；选择合法列值和存在的外键，不使用当前真实卷。先记录原缺口 RED。
2. 文件级设计先决定两个受限 DB issuer 的登录/SET ROLE 来源、窄表权与固定 search_path；该身份必须由部署配置提供，不从 HTTP actor/role 字符串推断。需要保持原 Store 的同事务资源写+Receipt 写，因此先在隔离克隆把整个命令走正向，再撤普通 runtime 直写。
3. 新 Alembic migration（检查唯一 head 后定名）逐表撤多余权限；Registry/Assignee Receipt 仅签发角色 INSERT/SELECT，普通 runtime 只 SELECT；Binding UPDATE 仅被明确批准的受信 Store issuer 使用，不能宽授 DELETE。若原 API 不能使用独立身份则失败关闭，不能临时给 runtime 返还 INSERT。
4. 专项负例：runtime 直写、跨租户、无 scope、伪造 Registry/Assignee Receipt、失效/重放；专项正例：Registry create/evaluate/update、Resolver/Tool 原命令仍保持同事务、幂等和 CAS。相邻回归与方案/代码复审后写 verification。实际当前库迁移、正式受限 API 与 Host 启用另波，需完整备份、ACL-faithful 克隆全链与零执行窗口。

现有可复用边界：`aip_network_issuer_connection.py`/`aip_budget_cost_connection.py` 已实现独立非 owner 登录、私有 passfile、精确库/角色/事务读回、`SET LOCAL ROLE` 后重新验证。AIP 应复用其**模式和检查**，不能复用 Network/Budget 的实际发行身份、凭证或宽授角色成员资格。独立 AIP 登录必须与普通 API 登录分离；给普通登录 `SET ROLE` 到 issuer 会使 ACL 形同虚设。先做单一 Assignee Receipt 的隔离切片，再扩到 Registry/三 Binding；不能把单表通过说成五表完成。

本轮不会碰当前原卷、不读取商城源、不启 worker/Provider/Host、不回放旧 Run、不 push。若仅完成原路径盘点/RED，明确留后续施工，绝不把计划/隔离夹具当正式身份成功。
