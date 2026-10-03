# E17-s3o-w-ao-b19｜共享 Receipt Capability 发行隔离文件级方案

## 上位与当前合同

- 231 四层/签名安装、BIND-1 31 要求租户、CAS、幂等、同事务 Receipt、非 owner 独立发行身份。b8/b12 已在 Tool 证明全表撤共享 Receipt INSERT 会伤其他合法 operation，DB session/operation 与事务配对必须共同约束。b17/b18 的忠实 ACL clone 保持 runtime 对 Receipt INSERT=true，适合先复现当前缺口。
- 原库只读：`aos_runtime` 对 `aip_capability_binding` SELECT/INSERT/UPDATE 和 `aip_agent_registry_receipt` INSERT 均 true；当前 Receipt 6行均 `agent_instance.create`，代码另有 Agent/Skill/Capability/Run/Content 等 operation。`RegistryIssuerConnectionFactory(capability_lifecycle)` 强制 runtime Receipt INSERT=false，因此当前实例角色即便创建也会失败；不可只修改 Python 身份门放行。
- 原 Capability Store 的 Receipt `result_ref` 仅资源类型/ID，`revision=None`；一条同租户既有 Binding 的旧 Receipt 无版本快照。直接照搬 b12 test-only `xmin` 探针会形成未经复审的公共持久协议，不在当前库写迁移。

## RED 与最小协议候选

1. 在 b17 新隔离 PG，以原 `aos_a0v_runtime_20260912` 独立登录后 `SET ROLE aos_runtime`、设置 `org-org/dev-project`，在单事务尝试 Capability/普通 Receipt，主动回滚。首试连接已被 DB CONNECT 拒绝 exit2；原库只读核所有非 owner runtime 成员 LOGIN 的 CONNECT 均 false，故**不得声称当前直接非 owner 登录能伪造**。保持该数据库入口门；改由当前可连的 `aos_app` 会话 `SET ROLE aos_runtime` 在新克隆事务内测试表级许可与两类 operation，明确 session_user=owner 的局限。不得写 dev-org 或当前库。
2. 只读核当前 `CapabilityBinding` 表/Receipt 约束、Store 三类 operation 的资源/结果引用及 `RegistryIssuerConnectionFactory` 权限门。提出 DB 级专用 operation 白名单、真实 session_user、同事务 Binding 版本/租户配对及 runtime 其他 operation 保留的精确协议；明确现有 Receipt 无 version、更新/评测并发和重放如何处理。
3. 公共持久合同未定前，仅落 RED/方案复审和失败闭合，不以 test-only trigger 当正式 GREEN；先将 DB CONNECT 精确授予、非 owner 正式 Reader/issuer/OIDC 与共享 Receipt operation 约束作为**不同安全门**。可并行推进不依赖该合同的配置/Reader 当前切换项；生产迁移、角色 ACL、API 发行路径待另波方案/RED/回归与当前安全窗口。

验证为隔离 PG RED/ROLLBACK＋原库只读 operation/ACL 回读；无生产代码/UI改动不重复浏览器。落 verification、精确 m1 提交、AOS/Prime/D-waves 同步后进入独立主线。当前真实库只读、Host/worker/Provider关，`org-org/dev-project` 唯一正向、`dev-org` 零副作用；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
