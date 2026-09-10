# AR2-7E 八工作台入口与失败关闭浏览器验证

日期：2026-09-10
分支：`m1`
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`
对应方案：`ar2-7e-eight-workbench-browser-plan.md`
执行器：`ar2-7e-eight-workbench-browser.mjs`
机器证据：`ar2-7e-eight-workbench-browser.json`
结论：`AR2_7E_EIGHT_WORKBENCH_ENTRY_MATRIX_GREEN`

## 1. 结果

```text
positivePassed=24 / positiveTotal=24
negativePassed=13 / negativeTotal=13
nonGetWorkshopRequests=0
pageErrors=0
consoleErrors=0
expectedNetworkConsoleErrors=264
stoppedEarly=false
horizontalOverflow=0 / 37
unauthorizedEnabledHeaderActions=0
screenshots=37
```

正向矩阵覆盖八条 canonical route × `1280×720`、`1440×900`、`1920×1080`。每个单元均回读：当前 module Shell、专用页头、8 个安装目录导航、唯一 active、唯一 H1、侧栏折叠恢复、精确 tenant header、页面业务读取失败关闭和无根级水平溢出。

反向矩阵覆盖八条空目录直达、Catalog 403、Catalog 503、声明 legacy replace、未声明/卸载 legacy、`dev-org/dev-project` canary 空目录。反向入口没有专用壳层、静态八菜单旁路或提前业务读取。

## 2. 诊断过程

1. 首次目录夹具把 operations legacyRoutes 写成非字典序，Catalog 解析器正确失败关闭；修正夹具稳定顺序，未修改产品。
2. Chrome 把每个预期 403/503 写成 `Failed to load resource` console error。按补充方案逐条保留到 `expectedNetworkConsoleErrors`，其余未预期 console error 仍为 0 并阻断。
3. 首轮完整机器结果暴露 operations 新建处理在空 actionTypes 下仍可用。该结果未被当作 GREEN；完成 `AR2_7E_HEADER_ACTION_AUTHORITY_GREEN` 后从头重跑，最终 37/37 PASS。

## 3. 隔离和无效果边界

- 8434 只提供当前 m1 Web 资产；所有 `/api/v1/**` 均在独立浏览器 context 内确定性拦截。
- 正向 Catalog 投影八个已安装 module；业务读取统一 403，明确证明本轮没有读取真实 `org-org/dev-project` 经营数据。
- 264 条预期网络提示与隔离拒绝响应逐条留在 JSON，不是被删除或忽略；HTTP 路径、状态与请求租户头可回读。
- 所有 Workshop 请求均为 GET。没有 Provider、费用、真实业务 mutation、外部发布、共享/生产迁移或 push；canary 没有获得正向目录。

## 4. 累计验证

```text
Web full suite: 280 files / 2507 tests PASS
Web production build: PASS / 375 modules
verify_closure.py --phase ar2-7:
  scannedPythonModules=1711
  classifiedModules=93
  migratedModules=57
  hashErrors=[]
  unclassifiedForwardDependencies=[]
  unclassifiedReverseCallers=[]
  bundleCrossLayerImports=[]
  dynamicReferenceErrors=[]
git diff --check: PASS
```

## 5. 限制与下一步

本矩阵证明的是安装入口、壳层、失败关闭、响应式布局和无效果边界。页面业务读取刻意拒绝，因此它不冒充八页 ready 数据和全部业务交互浏览器验收；丰富页面行为由现有 2507 项组件/合同测试保护，7E 下一切片仍需使用合同有效的隔离 ready/empty fixture 完成逐页只读业务交互矩阵。只有后续矩阵和 Prime 增量复核也通过，才允许生成 7E 整波 GREEN 与 authority CAS。
