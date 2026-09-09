# AR2-7D 累计 Asset Registry 修复验证

日期：2026-09-10
分支：`m1`
施工基线：`7d17e469`
结论：`AR2_7D_CUMULATIVE_ASSET_REGISTRY_REMEDIATION_GREEN`

## 1. 范围与边界

- 本切片处理累计 `tests/asset_registry` 首轮的 16 个失败，不关闭 runtime 签名、隔离生命周期、租户或 generation/epoch 校验。
- W1/M5 历史控制测试使用显式 `declarative_only` 签名副本；仓内当前三个 ecommerce bundle 及默认 copy/sign 路径仍保留 runtime/backend，由 D6D2 与完整 extension runtime 验证。
- 通用 `asset_registry/control_wiring.py` 不再静态导入 ecommerce 领域实现；具体 `EcommerceGrowthDisableDependent` 只在 `main.py` 组合根构造，并被 disable service 与 production runtime host 复用。
- 无真实租户装卸、业务 mutation、Provider、费用、共享/生产迁移、外部发布或 push。

## 2. 修改文件

- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7d-cumulative-asset-control-acceptance-plan.md`
- `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/dynamic-reference-phases.json`
- `services/aos-api/aos_api/asset_registry/control_wiring.py`
- `services/aos-api/aos_api/main.py`
- `services/aos-api/tests/asset_registry/m5_bundle_support.py`
- `services/aos-api/tests/asset_registry/m5_control_support.py`
- `services/aos-api/tests/asset_registry/test_control_wiring.py`
- `services/aos-api/tests/asset_registry/test_m5_ecommerce_boundaries.py`
- `services/aos-api/tests/asset_registry/test_m5_ecommerce_bundle_contracts.py`
- `services/aos-api/tests/asset_registry/test_m5_ecommerce_bundle_loader.py`
- `services/aos-api/tests/asset_registry/test_workshop_module_contracts.py`
- `services/aos-api/tests/extension_runtime/test_production_runtime.py`
- `services/aos-api/tests/extension_runtime/test_runtime_startup_composition.py`

## 3. 验证结果

| 验证 | 结果 |
|---|---|
| 16 项失败对应的聚焦非 PostgreSQL 集 | `83 passed, 7 warnings in 8.46s` |
| 历史 M5 PostgreSQL 邻接集 | `11 passed, 7 warnings in 13.56s` |
| `services/aos-api/tests/asset_registry` 全量 | `868 passed, 7 warnings in 53.33s` |
| `services/aos-api/tests/extension_runtime` 全量 | `1280 passed, 7 warnings in 158.90s` |
| Python compile / JSON parse / `git diff --check` | PASS |
| `verify_closure.py --phase ar2-1` | `1710 scanned / 93 classified / 57 migrated`，六个错误数组均为空 |
| `scripts/memory/memory-validate --json` | `AOS-000571 / GREEN / 865 receipts / 2226 events / 846 task receipts` |
| 隔离 PostgreSQL schema 与 OCI 残留 | 空 |

Pytest 的 7 条 warning 均为既有 Pydantic 字段遮蔽和 Starlette TestClient 弃用提示，本切片未新增 warning 类别。聚焦集退出时出现一条 JDBC 缓存 logger 在 pytest 捕获流关闭后的既有清理日志，不影响退出码或断言。

## 4. 动态清单复核

- `main.py` 的组合根注入改变文件 SHA-256；仅把 `ar2-1` 当前态哈希更新为 `5f0d43ceeab2daa400f073eab627d4e2aacb422374b9e2ee9b503ede33f96bfc`。
- `ar2-0` 冻结哈希保持 `206d335cac09dea1a7a47e8a17c927797e8aaeb212e3e44948309c45872722e2`，未改写历史基线。
- `verify_closure.py --phase ar2-7` 仍确定性报告 10 个预期红项：旧 domain Router/manifest、Web LegacyFallback/静态页面和静态八菜单尚未最终切换。这些红项属于后续 7D 受控单写切换，不能由本切片关闭。

## 5. 风险与下一步

- 本切片没有改变数据库结构或执行共享迁移；没有把历史声明式夹具用于当前 runtime 正向证明。
- production lifespan 注入了具体 dependent；其他直接构造通用 control plane 的调用者若不需要 ecommerce dependent 可继续省略，保持原兼容行为。
- 下一步继续 AR2-7D 累计 N1～N7 受影响集与 Web 全量门；随后完成资产控制三视口验收，再处理 `ar2-7` 的 Router/Web 最终切换红项及封板复核。
