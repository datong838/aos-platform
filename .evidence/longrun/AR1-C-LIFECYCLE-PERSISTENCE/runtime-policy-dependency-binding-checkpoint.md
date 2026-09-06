# AR1-c 运行策略依赖与配置绑定检查点

日期：2026-09-06

本检查点在 AIP 侧组合适配器中联合读取当前 RuntimePolicyRevision，以及其 network、egress、data classification、quota、budget policy 和最终原 BudgetRevision。所有可变 head 在调用者显式事务内以 `FOR SHARE` 固定，角色必须为 `aos_runtime` 且 Tenant GUC 精确匹配。原 DTO、列、规范化 hash、生命周期和有效窗口均逐项复核；配置 dataRefs 必须精确绑定策略的数据分级引用，配置 budgetRef 必须精确绑定 BudgetPolicyRevision 的原预算引用，network 的 egress 引用必须与运行策略一致。

独立 Prime 初审发现后置锁等待可能使前置依赖在返回前过期，以及反证矩阵不完整。实现已改为取得全部 head 锁后重新读取数据库时间并统一复核六个有效窗口；新增真实 `pg_blocking_pids` 后置 quota 锁等待跨前置 data 有效期反证，并覆盖 network/egress/quota/budget-policy 的 suspended、expired、规范化 payload 漂移及 network-egress 错绑。Prime 终审确认两项闭合，无新增确定问题。

验证结果：专项 31 passed；相邻配置、预算及原策略合同 108 passed；修正后累计 extension_runtime 与既定 asset_registry 安全集 822 passed、6 个既有 warnings、169.87 秒、exit 0。既有 JDBC 退出日志 closed-stream 提示仍存在，缓存计数为 0，不改变测试退出码。`git diff --check`通过。

环境边界：只在专用 `127.0.0.1:18432` 临时 schema 运行原 AIP7/AIP10 迁移和隔离数据；无共享迁移、真实业务数据修改、Provider、费用、发布或页面变更，浏览器验收不适用。此处只证明联合当前引用准入，不等同运行费用预留、全租户持久调度、业务自动闭环或 AR1-c 完成；新增业务场景仍为 0。
