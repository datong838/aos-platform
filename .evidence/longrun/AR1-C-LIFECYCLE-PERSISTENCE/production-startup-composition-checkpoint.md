# AR1-c 生产启动组合根检查点

- 日期：2026-09-06
- 基线：`c88d0a827d8efb65af1bd8e6c531c6ebdba22378`
- 租户/副作用边界：组合根构造不连接数据库、不读取租户、不启动 OCI、不领取 outbox、不创建预算 hold、不调用 Provider、不发布，也不新增公开路由
- 页面变化：无；浏览器验收不适用

## 已实现

FastAPI lifespan 在迁移模式确定后调用生产 `build_runtime_control_plane`，把一个不可变、进程级 `RuntimeControlPlane` 放入 `app.state.extension_runtime_control_plane`。外层统一 `try/finally` 登记并停止所有本应用创建的后台 task、清除组合根并关闭 JDBC；正常退出、业务体异常以及后台 task 已建立后的启动中途异常均走同一清理路径。组合根共享同一 `PostgresInstallationStore`、InstallationService、RuntimeReleaseRevalidator、RuntimeLifecycleService、RuntimeConfigurationService 与四源 ConfigurationAuthorization，避免生命周期和配置服务分别构造不一致的锁与 revalidator。

配置 permission 不读取 HTTP roles，也不默认放行；它在原事务内读取并锁定目标安装的当前 etag，再调用 `CurrentControlPermission(CONFIGURE_RUNTIME_OPERATION)` 复核持久成员资格、租户和目标 marking。`build_current_configuration_authorization` 已有生产调用点；当前 source fixture 从 `test_*` 收集模块移入可复用 case 模块。

## 验证

- 组合根与 lifespan 专项：11 passed；包含独立 Prime 首审发现的异常清理缺口及其两类回归反证。
- 当前四源隔离 PostgreSQL 专项：21 passed。
- extension-runtime 非数据库累计：265 passed、429 skipped；跳过项均受专用 PG/OCI 显式开关保护。
- 编译与 `git diff --check`：通过。
- 一次扩大的 extension-runtime + asset-registry 诊断先因专用测试数据库瞬时 1 GiB 容量耗尽而产生 47 failures/161 setup errors；精确删除 4 个遗留 `ar1c_*` 临时 schema 后容量恢复。随后无 PG 开关的全目录诊断为 1107 passed、429 skipped、20 failed；20 项均属于既有 M4 legacy integration fixture 与当前 runtime-only 安装拒绝规则不一致，不在本次生产组合根差异中，不能计入本波绿色结论，已作为后续兼容性清单输入。

## 结论与边界

本检查点闭合“正式四源配置 primitive 在生产启动树没有调用点”的缺口，只证明部署进程能安全装配控制服务。它没有启动持久消费者、全租户扫描、预算预留、Provider 或业务任务，因此业务场景仍为 0，不能声称八大工作台已自动工作。下一波进入持久宿主启动/停止协议、租约与重启消息重投；M4 legacy fixture 与 runtime-only 安装语义的 20 项诊断差异需在其所属兼容波中闭合。
