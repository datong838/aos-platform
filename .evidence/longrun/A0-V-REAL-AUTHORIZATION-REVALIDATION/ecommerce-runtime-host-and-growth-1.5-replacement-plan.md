# Ecommerce runtime host 与 growth 1.5 replacement 方案

日期：2026-09-12

## 当前状态

Registry 已唯一 published growth 1.5.0，持久 signed root 同时包含 1.4.0/1.5.0。正租户只有一个 Installation：revision 3、state `approved`、growth 1.4.0；负租户 Installation 为 0。正式 replacement 的 `currentInstallationRef` 只能引用 active revision，因此不能从当前 approved 1.4 直接生成 1.5 replacement。

18181 是 2026-09-11 启动的诊断 API，明确关闭 extension runtime host；8434 只是前端。隔离库只有超级用户 login，`aos_runtime` 与 `aos_extension_directory` 都是 NOLOGIN，host identity/assignment 为空。生产 selector 要求 directory/runtime/web 三个不同的非特权 login principal、同一数据库 authority、互斥角色 membership；当前不满足。

四来源配置授权现为：runtime/data/egress/network/quota/budget 实体有部分当前值，但 frozen ResponsibilityPlan=0、有效 BudgetPolicy=0。这个缺口允许 preparation 与 schema verification 独立推进，但 enable 必须 fail closed，后续通过真实经营参谋计划与当前预算授权补齐。

## 实施顺序

1. 新增单用途 runtime-host bootstrap/launcher。apply 必须锁定 `colima-aos-extension / aos-a0v-recovery-pg / aos_meta_head`，先备份；生成三个随机口令，只写仓外 `0600` 文件。创建 `aos_a0v_web_20260912`、`aos_a0v_runtime_20260912`、`aos_a0v_directory_20260912` 三个 LOGIN、NOSUPERUSER、NOBYPASSRLS 主体；runtime 仅继承 `aos_runtime`，directory 仅继承 `aos_extension_directory`，web 两者都不继承。
2. 最小授权：directory 只调用 `extension_runtime_read_host_assignments()`；runtime 通过既有 `aos_runtime` 角色在 tenant transaction 内工作；web 只用于 host 三平面身份探针，不承载诊断 API 请求。启动器内的 `db.get_dsn` 指向该 web identity，因此 selector 检查的是宿主自身真实 web plane；诊断 API 继续隔离、host=0。
3. 用现有 `extension_runtime_bind_host_identity` 与 `extension_runtime_set_host_assignment` SECURITY DEFINER command，固定 host id、actor、request hash、CAS 和 idempotency key；仅 assignment `org-org/dev-project`，负租户保持空。默认 preflight，重放零 revision。
4. Runtime 控制命令的请求角色必须与 `meta_membership` 当前持久成员一致。保留已有 `user:dev=owner` 不变；单用途执行器依照既有 Membership 服务的 `meta_membership` + `twa_ws_member` 双写及 `twa_audit` 审计语义，为主体 `a0v-ecommerce-growth-1.4-runtime-owner` 新增 `admin`，授权 actor 记录为 `user:dev`；正租户恰好一条，负租户为零，重放不更新。禁止用请求体里的临时角色绕过当前成员检查。
5. 宿主作为独立本地进程运行，显式注入三 DSN、`AOS_EXTENSION_OCI_CONTEXT=colima-aos-extension`、持久 bundle/trust root 与 platform；启动前 selector 必须 ACTIVE，退出时 graceful stop。凭据不进入命令行、Git、Receipt 或日志。
6. 对现有 1.4 approved Installation 创建唯一 `runtime-apply` operation；host 消费 outbox、启动三个 signed OCI member并提交 `runtime_preparation`，Installation 到 applied。随后创建 `runtime-verify`，同一 live owner 做当前 schema/release/permission检查并到 active。此过程不调用任何业务 operation 或 Provider。
7. 读取 active 1.4 的 exact installationId/revision/lockHash/overlayRevision 作为 `currentInstallationRef`，解析 growth 1.5 Composition；permission/migration/contribution diff 必须符合预期。maker 创建/submit，checker 独立 approve，再按同一 runtime apply/verify 形成 1.5 active replacement；激活时 predecessor 被 shadow，保留 rollback 链。
8. enable 必须在当前四来源授权全绿后执行。ResponsibilityPlan 由经营参谋基于用户给定材料形成真实计划并冻结；BudgetPolicy 使用用户“不限费用、聚焦功能”的明确开发授权，但仍通过既有 Policy Owner/Receipt 发布，不直写表。配置 target 必须引用当前四来源 exact revision；任何过期、缺失或歧义都阻断。

## 修改范围

- `scripts/a0v_ecommerce_runtime_host_bootstrap.py`
- `scripts/a0v_ecommerce_runtime_host.py`
- 对应 `services/aos-api/tests/extension_runtime/`
- 后续单用途 1.4 activation 与 1.5 replacement 执行器
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 停止与回滚

同一阶段失败两次或 OCI cleanup outcome 不明时停止该阶段并只读核验，禁止重发。host bootstrap 可先 revoke assignment、停宿主，再禁用 identity；login roles 只有在无连接、无 membership/owner 依赖时才删除。1.5 replacement 未 active 前不改变 1.4 active 指针；active 后按正式 rollback operation 恢复 predecessor，不直接改指针。

## 本波退出条件

三身份 probe/assignment/重放/负租户隔离全绿；独立 host ACTIVE 且可优雅停止；1.4 signed preparation 与 verify 形成 active baseline；1.5 exact replacement active；运行绑定、9 个 growth operation、generation/epoch/fence 可读。若四来源仍缺，则明确停在 verified/active-but-disabled 边界并立即进入授权补齐波次，不把测试绿当业务完成。

## 2026-09-12 运行发现与改线

1.4 首次真实 preparation 在签名与成员权限检查之后，由 Session exact-registration 阻断。静态复核确认三个运行包的后端分别注册 1/2/9 个 API，但其签名 Manifest 没有对应 API contribution；Growth 仅声明 navigation/UI。该 1.4 Installation 从未 active，失败 Operation 已终结，三个资源租约全部 `released` 且 `observed_release=true`，无遗留容器。

不得过滤 observed API、放宽 exact registration、修改已发布 1.4/1.5 字节或伪造 active 基线。后续改为：

1. 保留 1.4 的失败 Receipt，使用正式 uninstall 控制路径移除这个从未 active 的 approved Installation。现有状态机只接受 `active -> uninstalled`，因此补齐受限的 `approved -> uninstalled`：必须无 Runtime Binding、没有未终结 Runtime Operation，且历史 resource lease 全部 `released + observed_release=true`；仍由 Installation Command Receipt 幂等审计。约束同时落在应用层 guard、数据库不可变 revision trigger 与完整历史领域模型，任何一层缺失或读到不安全状态都拒绝提交；uninstall Evidence 明确封存真实的 `fromState`。active 路径继续强制 disable/detach/uninstall Receipt，不共享这个分支。
2. 新建不可变版本 `domain.ecommerce.core/1.2.0`、`platform.ecommerce.niushop/1.2.0`、`solution.ecommerce.growth/1.6.0`，在签名 Manifest 中逐项声明后端实际注册的 1/2/9 个 API；operations-base 1.2.0 不变。
3. Candidate preflight 必须比较 Manifest API contribution 与后端 registration 的 operationId/method/path/mode 全量集合，资格阶段增加真实 persistent Session registration/heartbeat；只做 image admission 不再足以判绿。
4. 新版本完成 build、签名、Registry 发布后，从 `currentInstallationRef=null` 创建新的 first Installation，再由独立 Host 完成 apply/verify。只有这个合法 active 基线形成后，才进入 configure/enable 与真实业务链。
