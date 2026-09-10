# AR2-7E 八工作台有效数据只读交互验证

日期：2026-09-10  
分支：`m1`  
方案基线：`acbe9e2a`  
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`

结论：`AR2_7E_EIGHT_WORKBENCH_CONTRACT_VALID_READ_ONLY_BROWSER_GREEN`

## 1. 实施结果

- 新增独立执行器 `ar2-7e-eight-workbench-ready-browser.mjs`，未修改产品源码，也未改写已封存的入口/失败关闭执行器。
- 八页使用现行客户端 parser 可接受的合同有效响应：主视图为 degraded/可信空，Catalog 为已安装；AIP、SourceReadiness、场景、贡献、调查和内部草稿补充读取均使用隔离的只读空/blocked 响应。
- fixture 不含真实经营事实；`permissions.actionTypes=[]`。浏览器路由层拒绝全部非 GET，未触发 Provider、发布、外部业务动作或内部草稿提交。
- 每个页面使用独立 context，在 `1280×720`、`1440×900`、`1920×1080` 三视口执行，合计 24 个单元和 24 张非空全页截图。

## 2. 页面专项读数

| 页面 | 只读交互 | 三视口 |
| --- | --- | --- |
| 任务总控 | 11 个状态选项；切换“已完成”后恢复“全部状态” | 3/3 PASS |
| 内容活动 | 活动策划、内容日历、日常模板三个业务视图逐项切换 | 3/3 PASS |
| 统一运营 | 四个待办分类逐项切换；搜索 `payments` 后清空恢复 | 3/3 PASS |
| 达人邀约 | 五个业务视图逐项切换；隔离检索后清空恢复 | 3/3 PASS |
| 多媒体生产 | 种草文案、短视频、数字人直播三个类型逐项切换 | 3/3 PASS |
| 经营参谋 | 生意探究只读与七个经营视图共八项逐项切换 | 3/3 PASS |
| 价格治理 | 同款价格治理、竞品比价、调度控制台逐项切换 | 3/3 PASS |
| 客户关系 | 客户最小投影、客户分群、生命周期旅程、对话与批次逐项切换 | 3/3 PASS |

各单元同时验证：八项安装目录、唯一当前导航、唯一 H1、页面专项文案、页头动作 authority、侧栏折叠恢复、精确租户头和无水平溢出。

## 3. 浏览器机器证据

`ar2-7e-eight-workbench-ready-browser.json`：

- `result=PASS`，`passed=24/24`，`screenshots=24`，`stoppedEarly=false`
- `nonGetWorkshopRequests=0`
- `unknownGets=0`
- `tenantHeaderDrift=0`
- `http5xx=0`
- `pageErrors=0`
- `consoleErrors=0`
- `horizontalOverflow=0`

执行器曾按“两次同页连续失败即停止”规则分别在任务总控、统一运营、达人邀约、多媒体、经营参谋和价格治理处停下；每次只补齐现行 parser 合同或纠正验收选择器，再从首项重放。最终证据只保存完整 24/24 结果，失败诊断截图已移除。

## 4. 回归与闭包

- 八页专项：8 files / 106 tests PASS。现存 React `act(...)` 警告为测试环境既有 stderr，不影响退出码和断言结果。
- Web 全量：280 files / 2507 tests PASS。
- production build：TypeScript + Vite PASS，375 modules transformed。仅保留既有 chunk-size warning。
- `verify_closure.py --phase ar2-7`：扫描 1711、分类 93、迁移 57；hash、正反依赖、跨层 import、动态引用错误均为空。
- `git diff --check`：PASS。

## 5. 一致性与边界复核

- 实现与方案一致：独立 fixture 执行器、24 单元、八页专项只读交互、精确租户、无写请求、机器证据和截图均已具备。
- 本证据只证明生产 Web 在合同有效的隔离可信空/blocked 投影下可读、可切换并失败关闭；不证明真实 `org-org/dev-project` 经营数据已接入，也不把 fixture 当作真实链路证据。
- 本切片不授权真实租户 mutation、Provider、费用、发布、共享/生产迁移或 push；`230 L0` 继续挂起。
- 仍需完成 7E 增量 Prime 只读复核与整波累计对账，才能生成 Delivery Receipt 和 authority CAS。本切片不单独宣布 7E 整波完成。
