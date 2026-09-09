# AR2-7D 最终 Dispatch 与安装目录导航切换验证

日期：2026-09-10
方案：`ar2-7d-final-dispatch-navigation-cutover-plan.md`
结论：本切片通过

## 1. 实现结果

- 生产 Router manifest 从 549 项收敛为 547 项，只登记 `aos_api.routers.extension_dispatch`；生成聚合与 manifest 完全一致。
- `extension_dispatch` 有效路由共 49 条：保留两个历史电商 Router 的 48 条 GET/HEAD 只读投影，移除 66 条历史写方法，并唯一挂载 `/v1/ecommerce-growth/operations/{operation_id}` Canonical POST。
- Canonical POST 继续调用既有 `EcommerceGrowthCanonicalRouter`；本切片没有新增领域 SQL、写 Handler 或第二套 runtime registry。
- `/workshop/*` 统一进入 `EcommerceWorkshopHost`；订单/库存静态页面回退已删除。侧栏仅遍历 `catalog.modules`，空目录与目录失败均不再伪造八个已安装入口。

## 2. 专项与累计验证

| 验证 | 结果 |
|---|---|
| Router/manifest/Canonical HTTP 专项 | 17 passed；2 subtests passed |
| 受影响 Workshop、经营探究、Router API 累计 | 58 passed；2 subtests passed |
| Web 聚焦路由/导航/Host | 18 passed |
| Web 全量 | 280 files passed；2501 tests passed |
| Web production build | 375 modules transformed；build passed；仅既有 chunk-size warning |
| `extension_runtime` 全量（一次性全迁移数据库） | 1253 passed；30 skipped；0 failed |
| `asset_registry` 全量（一次性全迁移数据库） | 868 passed；0 failed |
| Python compile / Router generator check | passed；547 manifest entries matched |
| `verify_closure.py --phase ar2-7` | 1711 scanned；93 classified；57 migrated；五类错误全部为空 |
| 工作区检查 | `git diff --check` passed；残留 `aos_test_*_ti4_test` 数据库 0 |

## 3. 失败运行与纠正

1. 首次后端专项未设置重启后的有效数据库端口，测试会话尝试连接 5433 并拒绝；改用 18434 隔离 PostgreSQL 后专项通过。该次没有进入测试体，不计代码失败。
2. 首次 Web 全量为 2499/2501：两个新增断言错误地期待 fixture 首项名称，并把全局侧栏“订单管理”误当旧页面正文。断言改为真实 fixture 名称，并限定检查 `.ecommerce-workshop-host-state`；产品实现未因此改变，重跑 2501/2501。
3. 首次 `extension_runtime` 错用只含扩展专项结构的共享管理库，1243 passed / 30 skipped / 10 failed；10 项均为公共基表不存在。随后使用会话自建、全迁移、自动删除数据库重跑，1253 passed / 30 skipped / 0 failed。没有在共享库补表，也没有把该环境运行计为通过。
4. 首次独立 Codex 只读复核为 BLOCK：`NAV_ITEMS` 仍公开 `/workshop/orders` 与 `/workshop/inventory`；目录为空或失败时没有 replacement，两个旧链接反而显示。既有测试只检查宿主正文，未检查全壳。新增全壳空目录/失败态断言先得到 2 failed / 10 passed，精确复现后把两条旧深链标记为静态导航隐藏；路由本身和安装目录声明的 legacy redirect 均保留。聚焦回归随后为 35/35，通过后 Web 全量为 280 files / 2502 tests。

## 4. 一致性与风险复核

- 与方案一致：生产聚合只有通用入口；旧读取保持，旧写入不可达；Web 入口和菜单均由当前安装目录决定。
- 与 D1～D6 一致：九项写派发仍使用同一 Canonical Router、DispatchRef、fence、generation、epoch 和 Receipt 权威；本切片未触碰数据库迁移或生命周期状态机。
- 已知限制：历史 Router 文件仍在源码中供只读投影和历史测试使用，但其 66 条写方法不在生产有效路由表。后续若新增历史 Router 写方法，`test_extension_dispatch_http.py` 会验证其不进入新入口。
- 旧订单/库存深链继续存在，但不再由静态导航公开；仅当当前安装目录的 `legacyRoutes` 明确声明时，Host 才将其重定向到 canonical 模块。空目录、403 或失败态均不会显示两条旧链接。
- 外部效果：Provider 调用 0、真实业务 mutation 0、生产迁移 0、外部发布 0；`230 L0` 继续挂起。

## 4.1 导航红项修复后的新鲜验证

| 验证 | 结果 |
|---|---|
| 新增全壳断言 RED | 2 failed / 10 passed；旧订单链接在空目录与失败态均被实际捕获 |
| AppShell / 导航 / Catalog 聚焦 | 4 files / 35 tests passed |
| Web 全量 | 280 files / 2502 tests passed |
| Web production build | TypeScript + Vite passed；375 modules transformed；仅既有 chunk-size warning |
| `verify_closure.py --phase ar2-7` | 1711 scanned；93 classified；57 migrated；五类错误全部为空 |
| `git diff --check` | passed |

方案措辞同步纠正：生产写入口是一个参数化 Canonical POST path，九项是其固定 `operation_id` 集合，不再表述为九条 path。

## 5. 后续

本切片关闭 `ar2-7` 动态入口 10 个红项。继续执行 AR2-7D 最终全量证据复核与 authority CAS；通过后按 231-6 自动进入 AR2-7E 八工作台入口和浏览器矩阵，不把本切片单独声明为整波完成。
