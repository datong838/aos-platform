# SC4-5l6f1 DataRequirement Outbox 原路由验证

日期：2026-09-15

基线：`c9feb7ef`
范围：只读 Outbox → 原 Analysis/Occurrence/ProductEvent/SnapshotGroup 路由；不读取商城源、不生成 Evidence、不调用 Provider、不恢复 Run、不确认 Outbox。

## 实现

- 新增 `services/aos-api/aos_api/ecommerce_analysis_data_requirement_route.py`：
  - 只接受当前 `data.requirement.request` Claim；payload 四字段必须与 Claim 完全相同。
  - 数据库中的 Outbox/Delivery、attempt、lease token、lease deadline 必须仍与 Claim 相同且未过期。
  - 历史 Requirement revision 必须通过原 Store 完整 hash 回读，并且仍等于当前 Head、状态为 requested、无 blocker。
  - 原 AnalysisRuntimeReceipt 必须按 exact `runRef` 唯一命中、由原 Store exact 回读、仍为 PREPARING，并与 Case/cutoff 一致。
  - accepted occurrence、实际 recorded target Receipt、ProductEventOrigin、原 source run/actor、完整 SnapshotGroup/cutoff/binding 必须逐项一致。
- 新增 `services/aos-api/tests/extension_runtime/test_analysis_data_requirement_route_pg.py`：复用原全迁移私有数据库和 e6e 12 源链，测试夹具只建立同数据库 `aos_runtime + TenantScope` 连接，不注入生产凭据或放宽权限。
- `closure-manifest.md` 只追加该 Host 模块分类和初始 hash；未改历史 preHash、阶段规则或验证器。

## Red 与修复证据

1. 首次收集因目标模块不存在而 `ModuleNotFoundError`，证明测试先于实现。
2. 重启后默认测试 DSN 指向未运行的 5433；切换到既定隔离 PostgreSQL 18432。第一次误用不存在的 `aos_meta` 数据库，最终使用容器实际 `postgres` 管理库创建一次性测试库。未修改产品配置。
3. 初次完整运行因一次性数据库未配置生产 runtime credential 而在 Outbox claim 前失败；仅在测试中增加运行角色/GUC连接工厂。
4. 代码复核发现历史 exact revision 尚不足以授权，增加 `get_current == get_exact`；新增“领取后取消”反例，旧 Claim 被拒绝。

## 新鲜验证

- 路由正向：`1 passed / 76.23s`。
- payload 漂移 + 领取后 Head 取消负向：`1 passed / 76.24s`。
- 完整两项（增加 Head 守卫前）：`2 passed / 146.96s`；最终两个单项分别覆盖当前正、负实现。
- `py_compile`：新增产品模块与测试通过。
- `git diff --check`：通过。
- `verify_closure.py --phase ar2-7`：追加清册后为 `1953 scanned / 193 classified / 93 migrated`，五类错误全部为空。
- Prime/shared-memory：七个强一致投影 `CURRENT`，Codex eventual 投影保持 `PENDING_ASYNC`；`memoryctl validate` 为 `GREEN`，AOS-000573，1201 Delivery / 1183 Task / 2900 Event。

默认不带 `--phase` 的验证器会检查冻结的 `ar2-0` 历史 hash，并把 A0-V 后续合法演进报告为漂移；本波权威阶段仍使用 `ar2-7`。该失败不用于修改历史 hash。

## 退出边界与下一项

l6f1只闭合自然消费者的不可变路由入口。没有执行 l6f2 六策略安装态解析、l6f3 固定编排、l6f4 双 Receipt Outbox 完成、l6f5 生命周期接线或 l6f6 自然链/重启验收。下一项为 l6f2：从原快照组的当前已安装、已发布且可验证包读取六个 exact exported policy refs；candidate 工作树文件不能冒充安装态。
