# Runtime lifespan live scheduler 启停方案

日期：2026-09-12

## 目标

用真实 `RuntimeHost`、`RuntimeTenantAssignment` 和 `LiveInstallationScheduler` 补齐 API lifespan 的 ACTIVE
宿主启停合同。隔离 scheduler 返回空 pending descriptor，证明后台宿主至少完成一次 lifecycle tick，退出时
同一 host/scheduler 被完整停止，且零 owner、零 OCI。

## 军规

1. 保留既有 lifespan 生产代码；本波只补当前缺失的组合验证，不为测试增加生产旁路。
2. assignment 使用 exact TenantScope 和 concrete scheduler；pending directory 只返回空 tuple，factory 若被调用
   立即失败，从而证明无 pending apply 不会构造 owner。
3. 使用线程事件观测 `read_descriptors` 已发生，避免以 task 已创建代替真实 tick。
4. lifespan 内确认唯一 `extension-runtime-host` 后台任务与 ACTIVE 状态；退出后确认 host closing、scheduler
   closing、owners 为空、app state 清除。
5. 不连接数据库、不读取租户数据、不调用 OCI、不 claim/ACK；真实三平面数据库身份已由 9.39 PG 回归覆盖。

## 修改目录

- `services/aos-api/tests/extension_runtime/test_runtime_startup_composition.py`
- `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md`

## 退出条件与下一波

真实 host/scheduler 首 tick、唯一任务、graceful stop、零 owner/factory/OCI 反证通过；完整 startup/host 邻接
回归、hash、closure 和独立提交完成。下一波审计 1.5.0 candidate 所需的 immutable package/version、五门
operation 声明、signed artifacts 与安装前置条件，先形成可执行发布/安装清单，不直接复用 1.4.0。
