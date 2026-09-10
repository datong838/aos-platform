# AR2-7E 八工作台有效数据只读交互验收方案

日期：2026-09-10  
分支：`m1`  
基线：`8dc9cdb5`  
权威：`AOS-000572 / AR2_7D_RUNTIME_WIRING_CANONICAL_ROUTER_GREEN`  
状态：执行器编码前冻结

## 1. Rules 与目标

- 继续 `m1` 单人串行；以 closure manifest、动态引用阶段表、7E 已封存入口矩阵和页面现行解析合同为准。
- 本切片验证八个生产页面在合同有效、完全隔离的 ready/degraded/可信空数据下能够渲染并完成页面专项只读交互；不把入口级失败关闭截图重复当作功能验收。
- 浏览器主路径固定为当前 m1 Web `http://127.0.0.1:8434`，控制通道固定为 Playwright 驱动本机 Chrome；每个页面使用独立 context 和 `org-org/dev-project` 隔离会话。
- fixture 只表达结构和状态，不包含真实经营事实；任何非 GET 请求一律由路由层拒绝并计为失败。Provider、费用、真实业务 mutation、真实发布、共享/生产迁移和 push 均为 0；`230 L0` 继续挂起。
- 同一页面连续失败两次立即停止浏览器动作并先定位根因；不得弱化断言、伪造页面成功或用旧截图覆盖失败。

## 2. 计划新增文件

- 执行器：`.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/ar2-7e-eight-workbench-ready-browser.mjs`
- 机器证据：同目录 `ar2-7e-eight-workbench-ready-browser.json`
- 截图：同目录 `ar2-7e-ready-{page}-{width}x{height}.png`
- 验证说明：同目录 `ar2-7e-eight-workbench-ready-browser-verification.md`

不预设产品源码修改。若验收发现确定性产品缺陷，先另写缺口方案并提交，再执行 RED、最小修复和回归。

## 3. 数据与路由合同

- Catalog 返回八个已安装 module；`permissions.actionTypes=[]`，保持 7E 页头业务动作不可执行。
- 八个主 view 按现行 parser 提供合同有效的 ready、degraded 或可信空响应；补充 contribution/scenario/draft list 端点也返回合同有效的空/受限结构，不以 403 或 404 噪声冒充页面状态。
- `/me`、组织、工作区和 health 只返回隔离身份；记录每个请求的方法、路径和租户头。
- 未列入白名单的 GET fail-closed，并进入机器证据；全部非 GET 返回 405。验收结果要求未知 GET、非 GET、跨租户头、HTTP 5xx、page error 和非预期 console error 都为 0。

## 4. 页面专项只读矩阵

八条 canonical 路由在 `1280×720`、`1440×900`、`1920×1080` 共执行 24 个独立单元。每个单元验证 Shell、唯一 H1、八项目录、唯一当前导航、无水平溢出、侧栏折叠恢复和截图，并执行页面专项只读动作：

1. 任务总控：状态筛选/任务列表或可信空态、详情区域的只读可达性。
2. 内容活动：三个页签切换，正式输入与计划状态可读，不提交工作流。
3. 统一运营：筛选、搜索和可用详情入口只读切换，不创建处理。
4. 达人邀约：五类业务视图/筛选可读，内部工作流只展示准备状态，不创建或提交。
5. 多媒体生产：内容类型/页签可读，生产与交付准备区不导出、不创建 Proposal。
6. 经营参谋：分析页签逐项可达，调查和学习补充保持只读。
7. 价格治理：三个页签可达，研究与处置贡献只读。
8. 客户关系：四个页签可达，生命周期和触达贡献只读。

对页面没有可点击实体的可信空态，必须验证空态文本和页面专项区域；不能为了制造交互而写入 fixture 业务事实。

## 5. 验证与退出条件

- 24/24 页面单元 PASS；每页声明的页签/筛选/专项区域都有机器读数，24 张新截图存在且非空。
- JSON 顶层为 PASS；`nonGetWorkshopRequests=0`、未知 GET=0、租户漂移=0、HTTP 5xx=0、page/console error=0、水平溢出=0。
- 运行八页相关专项测试、Web 全量测试、production build、`verify_closure.py --phase ar2-7` 和 `git diff --check`，结果全部 GREEN。
- 核对实现与本方案一致，并做 Prime 增量只读复核。只有累计 7E 条件全部满足后，主执行器才生成整波验证、Delivery Receipt 和 authority CAS；本切片不单独前推整波 GREEN。
