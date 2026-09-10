# AR2-7E 八工作台三视口浏览器验收方案

日期：2026-09-10
分支：`m1`
基线：`0176b9c8`
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`
状态：执行器编码前冻结

## 1. Rules 与范围

- 继续 `m1` 单人串行；浏览器主路径固定为当前 m1 Web `http://127.0.0.1:8434`，控制通道固定为 Playwright 驱动本机 Chrome，不切换已有登录浏览器。
- 本阶段只验证当前 tenant 安装目录驱动的八工作台入口、响应式布局、只读交互、失败关闭、legacy 声明和 canary 隔离。
- 7E 不提前读取真实 `org-org/dev-project` 经营数据。所有 API 响应使用脚本内隔离、确定性的 Catalog 与页面只读 fixture；浏览器证据只证明 Web 合同和路由，不替代后端 authority 证据。
- 路由层拒绝全部非 GET 请求并记录违规；Provider、费用、真实业务 mutation、真实发布、共享/生产迁移和 push 均为 0；`230 L0` 继续挂起。
- 同一阶段或同一页面连续失败两次即停止浏览器动作，先分析确定性根因；不得用旧截图或手工目测覆盖失败。

## 2. 新增文件

- 执行器：`.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7e-eight-workbench-browser.mjs`
- 机器证据：同目录 `ar2-7e-eight-workbench-browser.json`
- 截图：同目录 `ar2-7e-{page}-{width}x{height}.png`，以及反向入口诊断截图。
- 验证说明：同目录 `ar2-7e-eight-workbench-browser-verification.md`

不预设产品源码修改。若执行器发现确定性产品缺陷，先新增独立缺口方案并提交，再按 RED→最小修复→回归处理。

## 3. 固定正向矩阵

八条 canonical 路由分别在 `1280×720`、`1440×900`、`1920×1080` 执行，共 24 个独立页面视口单元：

1. `/workshop/cockpit`
2. `/workshop/content-campaign`
3. `/workshop/operations`
4. `/workshop/creator-growth`
5. `/workshop/media-studio`
6. `/workshop/analyst`
7. `/workshop/price-governance`
8. `/workshop/customer`

每个单元使用同一 `org-org/dev-project` 隔离会话和包含八个 module 的安装目录。页面主读取返回合同有效的 degraded/可信空数据；可选补充读取若不参与主页面可用性，可返回受控 404。每个单元必须验证：

- 当前 module Shell、module id、专用页头标题和 `is-workshop-primary-visual` 存在；
- 侧栏恰有八个 Workshop module，当前项唯一，公共导航与 Buddy 入口仍存在；
- 页面 H1 唯一，不出现路由级失败 Host；至少一个页面专项区域、页签或可信空/失败关闭说明可见；
- 可用页签执行一次只读切换；全局侧栏折叠后恢复；内容区和侧栏可滚动，根文档无水平溢出；
- page error、console error、HTTP 500 均为 0；所有 Workshop/API 业务请求均为 GET 且租户头精确；保存全页截图和 DOM/网络读数。

## 4. 固定反向矩阵

在 `1440×900` 追加以下入口：

- 空目录直达八条 canonical URL：均显示“模块未安装”，专用视觉 class、业务页头、目标 module 导航均为 0；
- Catalog 403 和 503：分别显示权限/读取失败状态，不回退静态八菜单，业务读取请求为 0；
- legacy `/workshop/orders`：只在当前 Catalog 对 operations 显式声明时 replace 到 `/workshop/operations`；空目录时保留原 URL 并显示未安装；
- `dev-org/dev-project` canary：Catalog 只返回空目录，不出现正向 module、页面数据、内部草稿或 Receipt。

反向项同样记录请求、错误、布局和必要截图。任何非 GET 请求、跨租户头、正向业务文案泄漏或静态菜单旁路都判 FAIL。

## 5. 退出条件

- 24/24 正向单元 PASS；空目录 8/8、403、503、legacy 声明/未声明和 canary 全部 PASS。
- JSON 顶层结果为 PASS，错误与副作用计数为 0；截图数量与矩阵一致。
- Web 相关回归、全量、production build、`verify_closure.py --phase ar2-7` 和 `git diff --check` 仍为 GREEN。
- Prime 对本次增量只读复核 PASS 后，才允许生成 7E 整波验证、Delivery Receipt 和 authority CAS；本执行器单独通过不宣布 `AR2_HOST_WIRING_CUTOVER_PLUGGABILITY_BROWSER_ACCEPTANCE_GREEN`。

