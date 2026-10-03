# E17-s3o-w-ao｜正式 Reader 生产接线与当前角色切换文件级方案

## 上位方案与当前事实

- 复习 231-4 数据/权限/迁移安全、231-9 栖月汇首链、AIP-7 22 与 BIND-1 31。上波 s3o-w-an 已用当前 `a0v_135` 全备在隔离 PG 恢复并验证独立 NOINHERIT Reader 正反链；当前真实库 `aos_current_preview_20260927` 仍只读，正式 `aos_aip_binding_readiness_reader` role=0，正式 OIDC/API 身份和 Registry issuer 未齐。
- 代码复审发现生产 `routers/aip_bindings.py` 的 `_CAPABILITY_SERVICE=AipCapabilityBindingService()`，构造器在未注入 `connect_factory` 时自动创建 `AipBindingReadinessService()`；该默认服务的 `PostgresBindingDependencyAuthority` 和 `AipModelRuntimeStore` 回退普通 `db.connect`。因此测试用独立 Reader 全链 GREEN 不能证明生产 preview/evaluate 正在使用独立身份。正式角色即使建成，也不会自动接入现路由。
- 正式受限 API 启动器还要求外部 OIDC、独立 API identity；当前预检 `EXTERNAL_OIDC_CONFIG_REQUIRED`。不能把 owner 预览进程、test-only 账号或隔离签名树当正式身份。Role/ACL 受控切换和 API/issuer 接线应分门验证，不能只造 DB role 就宣称当前绑定正向。

## 文件级步骤

1. **先封 owner 回退**：在 `services/aos-api/tests/aip/test_aip_binding_api.py` 增生产默认服务的 preview 负例，证明未给独立 Reader 时不能调用普通 owner 的 readiness；先 RED。仅改 `services/aos-api/aos_api/aip_capability_binding_service.py` 构造器去掉默认 `AipBindingReadinessService()` 回退，保留显式注入的独立 Reader 路径；现有 list/get/原已授权 create 状态和 Receipt 语义不得因本切片变化。相邻 API/Reader/PG 回归验证。
   相邻 `test_aip6_capability_run_handoff.py` 原先预期无 operational readiness 的 active 命令到达持久层后拒绝；去 owner 回退后改为更早的 `explicit readiness reader required`。只调整该负例的预期，仍核其不激活、不出 Receipt；不得用旧 owner Reader 恢复测试通过。
2. **配置与发行身份独立接线**：再审 `routers/aip_bindings.py`、`aip_registry_issuer_connection.py` 与正式启动器，形成一个受控私有配置入口。preview 仅读独立 Reader；evaluate 同时需要独立受限 issuer 和 Reader，不得借 owner 或 `aos_runtime`。缺其中任一项保持失败关闭。新入口先隔离原链 RED/正反与错租户、凭据丢失、权限漂移测试；不在当前 API 隐式生成角色/口令。
3. **当前库维护另门**：专用维护 runner 默认 dry-run、固定真实卷/库/代码头、18表白名单、FORCE RLS、NOINHERIT/NOBYPASSRLS/非 owner、私有口令文件及归属；克隆先证明事务回滚/重跑对账。当前库写入前新一致备份、独立全库恢复、零执行窗口与原安装/Receipt 摘要核验；切后只读角色/ACL/RLS/租户正反/签名安装及页面复验。没有正式 OIDC/issuer 时只声明 Reader DB 就绪，Host/worker/Provider继续关闭。

本波先执行第1项，避免继续以 owner 默认连接冒充独立 Reader；第2/3项按证据推进。无商城源读取、旧12 Run 重放、手工 Run、230 L0 或 push。
