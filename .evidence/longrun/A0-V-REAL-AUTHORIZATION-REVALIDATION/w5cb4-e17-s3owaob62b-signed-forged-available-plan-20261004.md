# b62b 文件级计划：签名安装下的 available 来源负门

## 依据

- 231-3 的有效准入依赖 current active Installation、当前绑定/代次和权限预算；BIND-1 的 tenant readiness 必须是 exact 当前依赖快照。b62 完整迁移隔离库已 RED，但尚未与 Growth1.13 真签名/安装/Registry 联合。
- b47 test-only 函数只写 blocked/PENDING；b49/b50 两向 Registry 撤销序列化，不能证明普通 issuer 无法伪造 available。当前库 a0v_135 只读。

## 文件级步骤

1. `services/aos-api/tests/extension_runtime/test_growth_signed_installation_full_schema_pg.py`：新增单一 `AOS_B62B_FORGED_AVAILABLE=1` 隔离模式，仅 Growth1.13，动态 strict xfail；签名加载、正式 Registry publish、active Installation 与 b47 blocked 原链先成立，再执行伪造负门。
2. `services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py`：测试专用普通 issuer 登录，限制租户与最小直接 Binding/Receipt ACL；对现有 b47 Binding version2 试写 available、自造 hash、evaluate Receipt，要求拒绝。临时角色/策略始终清理；若未拒绝，strict xfail 即为联合 RED。
3. 用本地 Growth1.13 签名 Receipt、无卷 `aos_test_*_ti4_test`、隔离 OCI 跑单模式；检查失败细节是否确为缺可信来源而非夹具错误；再跑 b48/b49/b50 相邻模式与 b62 单元回归。适用时仅按原浏览器证据保持禁入，不改页面。

## 风险和退出门

- 此切片只保留 RED，绝不授予生产 issuer `available` 写权或启 Host。签名夹具中的 test-only 角色/权限只在 disposable 库创建，不作为唯一136迁移模板。
- 后续真正 GREEN 必须同最终事务证明签名当前来源、八类依赖、Binding CAS/Receipt 与 revoke/replace 并发；当前实例另需正式凭证/角色、新备份/全恢复/零执行窗口。
