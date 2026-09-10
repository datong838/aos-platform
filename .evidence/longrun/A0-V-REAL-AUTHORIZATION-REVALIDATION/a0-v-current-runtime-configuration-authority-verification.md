# A0-V 当前 Runtime 配置权威验证

## 结论

2026-09-10 在隔离恢复库 `aos-a0v-recovery-pg/aos_meta_head` 使用生产 AIP Store 建立并重放七类 fail-closed policy/budget 权威。首次 mutation count=7，重放 mutation count=0；七个对象的 ID、revision、content hash 完全一致，`dev-org/dev-project` 对应计数持续为 0。

当前结果为 `A0V_CURRENT_RUNTIME_CONFIGURATION_AUTHORITY_BLOCKED`：六个调查职责所需 AgentInstance 全部仍是 provisioning，正式 `BusinessInvestigationAuthorityMaterializer` 拒绝生成可冻结的 ResponsibilityPlan。没有创建 legacy/简化计划，也没有越过职责依赖。

## 已建立权威

- egress：`a0v-ecommerce-egress-v1@1`，仅 `https://api.agnes-ai.cn:443`，region confirmed，public fallback=false，unknown=block。
- data：`a0v-ecommerce-public-catalog-v1@1`，只允许 `public_catalog`，七类敏感/未知分类明确禁止。
- network：`a0v-ecommerce-network-v1@1`，TLS required，exact 绑定 egress，public fallback=false。
- BudgetRevision：`a0v-ecommerce-hard-stop-budget-v1@1`，development/CNY，daily 10000 minor、monthly 100000 minor，hard-stop，unknown usage=block。
- quota：`a0v-ecommerce-quota-v1@1`，max concurrency=1、hourly=10、daily=50、queue、auto-scale=false、public provider fallback=false。
- budget policy：`a0v-ecommerce-budget-policy-v1@1`，exact 绑定 BudgetRevision，unknown usage/price=block，zero price=false。
- RuntimePolicy：`a0v-ecommerce-runtime-policy-v1@1`，deadline 10s、max attempts=1、fallback reasons 为空、kill switch=false。

上述有效期统一固定为 `[2026-09-10T00:00:00Z, 2027-09-10T00:00:00Z)`；金额和 network policy 只构成配置边界，不授予 Provider、模型或外部调用。

## 备份、效果与重放

- 本阶段独立 pre-mutation backup：`sha256:acc8b3e841b0421755919a35f646d77faaa1a618f2f44deec85a90e63d6f8595`，4,346,482 bytes。
- 首次/重放 Provider invocation：0。
- 首次/重放 external publication：0。
- 首次结果：`a0-v-current-runtime-configuration-authority-result.json`，SHA-256 `f63fa9d288c2cda2af502452c9dda941c87fe9074d41f0cf2f41330a9838f590`。
- 重放结果：`a0-v-current-runtime-configuration-authority-replay-result.json`，SHA-256 `2159d8a46565c01facbdeba1a4e79b69d1ce8298b2b295bf56d5d9e9bf48d75b`。

## 测试

- 脚本 preflight/目标库/固定窗口专项与 policy/budget/network/governance contract：57 passed。
- Store 扩展批次另有 10 项因默认旧开发库 `127.0.0.1:5433` 在系统重启后未运行而失败；该批不计 GREEN。
- 相同 Store 的实际隔离库首次与重放路径成功，覆盖了本阶段所用 publish、依赖重验、exact readback 与幂等 Receipt。

## 下一门

下一项是使六个已安装 AgentInstance 从 provisioning 进入 active。必须先补齐它们的 published SkillTemplate、skill binding、capability binding 和 RuntimePolicy exact 引用，并保持 Provider/模型/路由的 A0-V 独立门。六个实例 active 后重新调用正式调查 authority materializer，冻结 ResponsibilityPlan，再由四源 authorization 验真完整 ConfigurationDocument。

本验证没有启动 runtime、没有登记 schema Receipt，不是 runtime ready，也不是 A0-V 总体 GREEN。
