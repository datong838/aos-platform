# AR2-7D 最终 Dispatch 与安装目录导航切换方案

日期：2026-09-10  
分支：`m1`  
状态：编码前冻结

## 1. 权威与当前缺口

- 权威顺序为 `closure-manifest.md`、`dynamic-reference-phases.json`、`verify_closure.py`、当前 `m1` 历史。
- `verify_closure.py --phase ar2-7` 当前只剩 10 个动态入口错误：生产 Router 聚合仍登记两个旧电商 Router，Web 仍保留订单/库存静态回退，侧栏仍从静态八模块清单生成入口。
- D1～D6 已完成九项 Canonical Router、整组切换、签名安装/停用/卸载/重装、累计回归和资产控制三视口验收。本切片只完成代码级最终入口切换，不重复生命周期实现，不扩大外部授权。

## 2. 目标行为

1. 生产 Router manifest 只登记 `aos_api.routers.extension_dispatch`，不再直接登记 `ecommerce_workshop`、`ecommerce_business_investigations` 或 `ecommerce_growth_dispatch`。
2. `extension_dispatch` 挂载已经封存的单一参数化 Canonical POST 路径，由九个固定 `operation_id` 选择对应 HostService；旧电商 Router 只复制 GET/HEAD 路由对象以保留现有目录和只读页面投影，任何旧 POST/PUT/PATCH/DELETE 都不得进入生产路由表。
3. 九项写请求继续由 `EcommerceGrowthCanonicalRouter` 签发并重验 DispatchRef；本切片不增加第二个写服务、数据库写入或兼容直写。
4. Web 所有 `/workshop/*` 入口只进入 `EcommerceWorkshopHost`。旧 URL 仅由当前安装目录的 `legacyRoutes` 解析；未安装时显示宿主的不可用状态，不再静态加载订单或库存页面。
5. Workshop 侧栏严格按 API 已做租户、角色、权限和当前安装过滤后的 `catalog.modules` 排序渲染。目录为空、禁止或失败时不得伪造八个入口。

## 3. 文件范围

新增：

- `services/aos-api/aos_api/routers/extension_dispatch.py`
- `services/aos-api/tests/extension_runtime/test_extension_dispatch_http.py`

修改：

- `services/aos-api/aos_api/routers/domain_manifest.json`
- `services/aos-api/aos_api/routers/domain_aggregates.py`（仅由既有生成器对应 manifest 结果更新）
- `services/aos-api/tests/test_domain_router_manifest.py`
- `apps/web/src/pages/s2/ecommerce/routes.tsx`
- `apps/web/src/components/workshop/InstalledModuleNavigation.tsx`
- `apps/web/src/components/workshop/InstalledModuleNavigation.test.tsx`
- `apps/web/src/shell/AppShell.workshop.test.tsx`

旧 Router 文件继续保留为只读投影来源及历史专项测试目标，不删除领域实现或历史审计数据。

## 4. 验证门

1. Router 专项静态检查：新入口源文件只能组合路由，不能包含领域 SQL；生产有效路由包含一个承载九个固定 `operation_id` 的 Canonical POST path 和旧 GET，只读之外的旧方法均不存在。
2. Manifest/生成一致性：count、连续 order、domain count、生成 diff、运行路由库存与 OpenAPI 重复检查全部通过。
3. Web 专项：动态模块按 catalog 顺序显示；空目录与读取失败均为零 Workshop 菜单；旧 URL 有安装别名时跳转 canonical，无安装时不出现旧页面正文。
4. 受影响后端与 Web 累计回归、Web build、`verify_closure.py --phase ar2-7` 全部通过。
5. 复核无 Provider 调用、真实业务 mutation、生产迁移、外部发布；`230 L0` 维持挂起。

## 5. 停止与回滚规则

- 新入口若暴露任何旧写方法、Canonical path 重复或只读投影丢失，立即停止，不提交代码。
- 相同验证阶段连续两次出现同根因失败时，回到本方案补充根因与修正，不跨阶段绕过。
- 本切片以独立提交保存方案；代码和验证证据分别形成可回滚提交，不 push。

## 6. 独立复核红项修订卡（2026-09-10）

- 独立 Codex 只读复核确认：`apps/web/src/navigation/items.ts` 仍把 `/workshop/orders` 与 `/workshop/inventory` 登记为可见静态页面。`AppShell` 只在当前 `catalog.modules` 声明 replacement 时过滤；目录为空、403 或读取失败时 modules 为空，两个旧链接反而继续显示，违反本方案“空/失败零 Workshop 菜单”的退出条件。
- 既有无安装测试只把“订单管理”断言限定到 `.ecommerce-workshop-host-state`，没有覆盖全壳侧栏；验证文档也记录了因全局侧栏存在该文本而缩窄断言，不能视为通过。
- 最小修正：保留两条旧路由定义供深链兼容和目录声明的 legacy redirect 使用，但在静态导航源把它们标记为 `hidden`；当前安装的 canonical 模块入口仍只由 `InstalledModuleNavigation` 渲染。新增 AppShell 正反测试：已安装时只有 canonical 动态链接、没有两个旧静态链接；空目录与目录失败时全壳均无旧链接或任何动态 Workshop 模块链接。
- 新增修改文件：`apps/web/src/navigation/items.ts`、`apps/web/src/shell/AppShell.workshop.test.tsx`，并回写本方案与验证证据。退出条件为新增专项先红后绿、AppShell/导航聚焦测试、Web 全量、build、closure 与独立只读复核全部通过。
