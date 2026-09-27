# W5CB4 E15：当前安装包类型权威投影与通用动作禁入（2026-09-28）

## 上位与现场

复习产品 12 栖月汇方案、231/231-9 BG-00 与 231-3 运行包隔离生命周期。E13 通用 Apply 对运行包 409 且未提交；E14 `7bf2773a` 已让服务端返回 `RUNTIME_OPERATION_REQUIRED` 并在页面提示，但浏览器仍看到可点的通用 Apply。当前安装 approved/revision3/ETag3、active 空；Runtime Host/operation/binding0，来源/管道/Selection未建。不得因补 UI 禁入而启用运行 Host 或读取商城源。

## 文件级方案

既有 `asset_registry/legacy_runtime_boundary.py` 的 `legacy_content_predicate` 是多处当前安装消费者复用的 fail-closed 观测：仅 exact 所选版本 hash 与 manifest 都可信且不含 runtime 才返回 true；false 可能是运行包，也可能是 Registry 漂移，不得在前端擅自解释成已验证运行包。E15 用它在 `extension_runtime/runtime_view.py` 的**同一个租户只读事务**里对当前安装 revision/ETag 锁定后产生 `legacyContentEligible: true|false|null`；查询缺行/不唯一/漂移时为 null 或拒绝，不选“最新”猜测。响应 DTO `RuntimeInstallationView` 与 `apps/web/src/api/assetControl/types.ts` 同步新增可选读模型字段；绝不把它写回安装真源或改变幂等 Receipt。必要时更新 `asset_registry/control_wiring.py`，但优先复用现有连接与 `legacy_content_predicate`。

`apps/web/src/pages/s2/AssetBundlesPage.tsx` 只有在 runtime view 当前、无 stale/refresh、installationId/currentRevision/ETag 与安装详情一致且 `legacyContentEligible===true` 时才允许旧通用 Apply/Verify；false/null/读失败一律禁入并提示“运行包或 Registry 权威未核实，请走/核对下方运行实例”，不能把仅有 `allowedActions` 当包类型。`assetBundles/{InstallationActionPanel,installationActions}.ts*` 用显式门参数/禁用理由，保留 submit/approve/reject 和纯内容路径原行为。服务端原 `RUNTIME_OPERATION_REQUIRED` 围栏始终保留。

专项/累计测试：纯内容 true 正常、runtime false 禁入、Registry 行缺失/hash 漂移 false、租户/错 revision/ETag/stale/null 禁入、后端和前端 DTO、旧动作防重；TypeScript/构建、相邻 Registry/runtime PG 与前端累计回归。浏览器只读验收当前安装通用 Apply 禁用、运行入口仍单独展示，不点击 `runtime-apply`。方案/代码一致性及安全复审后 verification 落盘、m1 精确提交，更新 AOS/Prime 上下文；同日若代码已变再用最新 m1 与原命名卷完整重启 DB/API/Web 验证并继续 E16。

本波 9 步：1 上位复习；2 读模型/文件级确认；3 RED 与最小实现；4 专项；5 累计；6 浏览器；7 一致性复审；8 verification；9 提交/上下文/下一波。停止门：包类型未知或多行、权限/标记漂移、测试结果未知时 fail closed；不请求用户凭据、不造伪身份、不操作旧卷/旧 12 Run、不 push，230 L0 仍挂起。
