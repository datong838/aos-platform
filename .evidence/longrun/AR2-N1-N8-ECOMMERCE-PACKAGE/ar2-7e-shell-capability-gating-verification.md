# AR2-7E AppShell 安装能力门控验证

日期：2026-09-10  
分支：`m1`  
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`  
对应方案：`ar2-7e-shell-capability-gating-plan.md`  
结论：`AR2_7E_SHELL_CAPABILITY_GATING_GREEN`

## 1. 变更范围

- `apps/web/src/shell/AppShell.tsx`
- `apps/web/src/shell/AppShell.workshop.test.tsx`

`AppShell` 的四个专用视觉开关现在同时要求当前路径能匹配 Catalog 中已安装的 module。pathname 继续负责精确选择页头样式，但不再单独授予专用品牌、业务标题、动作或视觉 class。

未修改 Catalog API、Host 状态机、业务页面、后端、数据库、权限合同和路由。Provider 调用、真实业务 mutation、外部发布与生产迁移均为 0。

## 2. RED 证据

修复前运行：

```text
pnpm --filter @aos/web exec vitest run src/shell/AppShell.workshop.test.tsx
Test Files  1 failed (1)
Tests  5 failed | 12 passed (17)
```

五个失败用例分别覆盖空目录、读取失败、403、响应租户漂移、仅安装其他 module。每例正文 Host 都已失败关闭，但 `.p-app` 仍错误包含 `is-workshop-primary-visual`，精确证明静态 URL 绕过安装能力。

首次测试命令因系统重启后终端未继承 Node PATH 而在用例前退出，不计产品 RED；恢复固定本机运行时后取得上述有效 RED。

## 3. GREEN 证据

关联回归：

```text
pnpm --filter @aos/web exec vitest run \
  src/shell/AppShell.workshop.test.tsx \
  src/components/workshop/EcommerceWorkshopCatalogContext.test.tsx \
  src/components/workshop/EcommerceWorkshopHost.test.tsx \
  src/components/workshop/InstalledModuleNavigation.test.tsx
Test Files  4 passed (4)
Tests  30 passed (30)
```

Web 全量：

```text
pnpm --filter @aos/web test
Test Files  280 passed (280)
Tests  2507 passed (2507)
```

生产构建：

```text
pnpm --filter @aos/web build
tsc -p tsconfig.json && vite build
375 modules transformed
built successfully
```

阶段验证：

```text
python3 .evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/verify_closure.py --phase ar2-7
scannedPythonModules=1711
classifiedModules=93
migratedModules=57
hashErrors=[]
unclassifiedForwardDependencies=[]
unclassifiedReverseCallers=[]
bundleCrossLayerImports=[]
dynamicReferenceErrors=[]
```

`git diff --check` 通过。

## 4. 产品与方案一致性

- 当前 tenant 的 Catalog 存在精确 module 匹配时，八个主工作台继续使用既有专用壳层、唯一 active 导航和页面动作。
- Catalog empty/failed/forbidden/tenant mismatch 或只安装其他 module 时，正文继续由 Host 展示可信失败关闭状态，外壳恢复通用顶栏与品牌区，不暴露目标工作台业务控制。
- stale/degraded 情况只要仍保有同 tenant 的已安装 module 快照，继续保持既定只读页面能力；本切片未改变这项产品约定。

## 5. 风险与下一步

- 构建仍报告既有大 chunk 提示，本次只改布尔门控，不增加 bundle 依赖或体积。
- 本结论只关闭 7E 第一个确定性壳层缺口，不代表八页三视口浏览器矩阵或整波 7E 完成。
- 下一步按 `ar2-7e-pre-entry-readiness-inventory.md` 进入 8 页 × 3 视口浏览器矩阵，继续验证正向安装目录、空/403/失败、legacy 跳转和 canary 隔离。

