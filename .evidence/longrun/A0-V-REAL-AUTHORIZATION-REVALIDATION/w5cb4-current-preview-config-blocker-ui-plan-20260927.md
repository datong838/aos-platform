# W5CB4 当前安装配置阻断摘要与正式入口波（2026-09-27，编码前）

## 上位与现状

- 依据 231 BG-00/A0-V、231-9 exact 权限/预算/审批，以及 `w5cb4-current-preview-runtime-config-authority-inventory-verification-20260927.md`。当前唯一安装 approved 但 binding=0；八项正式配置在当前新库全为 0。HTTP 预览仅可浏览，不能把安装批准当业务启用。
- 产品要在安装页解释“缺什么、由谁配置、何处进入”，仍以当前租户和安装权威为准；路由存在不等于配置已生效。可导航的现成入口只有责任计划与配额。其他六项不得用静态假数据或默认策略填绿。

## 文件级最小切片

1. 后端 `services/aos-api/aos_api/extension_runtime/` 增加只读、租户作用域内的八项候选权威摘要；复用正式 head/revision 的 active/frozen/有效期条件。结果标记为“当前租户候选数”，不能冒充已绑定当前安装或可运行。未授权/SQL 错误返回 unknown，不把错误归零。`services/aos-api/aos_api/routers/bundle_runtime_installations.py` 增 GET，先核验该安装对 principal 可见，`Cache-Control: no-store`，无写库、无运行控制。
2. 前端 `apps/web/src/api/assetControl/runtimeInstallations.ts`、`types.ts` 与 `apps/web/src/pages/s2/assetBundles/` 读钩子/面板，只有 endpoint 当前读回且安装 ID/revision/etag 一致才显示候选数。未读到或过期显示“未核验”，不借历史截图或本地状态。责任计划链接 `/aip/production-contracts`、配额链接 `/aip/capacity`；其余标记“正式配置入口待建”。所有运行操作仍以现有服务端 allowedActions 控制，不新增执行按钮。
3. 后端测试：跨租户/不可见安装、八零、部分 active、过期、SQL 故障、不得写。前端测试：八缺口、unknown、身份漂移与原安装操作回归。运行 `AOS_TEST_RETAIN_DATABASE=1` 仅用于测试夹具，可自动清理隔离库依后到授权；不删任何业务库/卷/备份。
4. 专项与累计回归、HTTP/浏览器验收、方案代码一致性复审、verification→m1 精确提交。启用、Provider、商城源、旧 Run、230 L0 均不在本切片。

- 累计回归发现 `ASSET_CONTROL_OPERATIONS` 是冻结的 M2-B 23 项合同；本次新增**只读**摘要不改变该冻结注册表，在 client 中使用显式规范化安装 ID 和静态路径，避免把历史合同测试改数凑绿。

## 停止条件

- 若 App 只读角色没有八表 SELECT，不能改用管理员连接或前端常量；先补正式只读授权与测试，或将摘要保持 unknown。
- 若安装可见性不能在同一只读请求中核验，不公开跨租户计数；本波停在 RED 并记录正式修复任务。
