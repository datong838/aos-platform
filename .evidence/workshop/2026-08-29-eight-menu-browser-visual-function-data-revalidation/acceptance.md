# Workshop 八菜单浏览器视觉、功能与栖月汇数据复验

- Task：`WORKSHOP-EIGHT-MENU-BROWSER-VISUAL-FUNCTION-DATA-REVALIDATION`
- 租户：`org-org/dev-project`
- 日期：2026-08-29（Asia/Shanghai）
- 边界：浏览器与 API 均为租户内读取或零外部效果安全预检；未触发 Provider、发送、发布、调价或真实业务写入。

## 1. 方案与视觉稿逐页复核

以内置浏览器逐页打开并交替比较以下正式视觉稿与实际路由：

| 页面 | 视觉稿 | 实际路由 | 三视口截图 | 结果 |
| --- | --- | --- | --- | --- |
| 日常总控 | `workshop-task-cockpit.html` | `/workshop/cockpit` | 1280×720 / 1440×900 / 1920×1080 | GREEN |
| 内容活动 | `workshop-content-campaign.html` | `/workshop/content-campaign` | 同上 | GREEN |
| 统一运营 | `workshop-operations.html` | `/workshop/operations` | 同上 | GREEN |
| 达人邀约 | `workshop-creator-outreach.html` | `/workshop/creator-growth` | 同上 | GREEN |
| 多媒体 | `workshop-media-studio.html` | `/workshop/media-studio` | 同上 | GREEN |
| 经营参谋 | `workshop-analyst.html` | `/workshop/analyst` | 同上 | GREEN |
| 价格治理 | `workshop-price-governance.html` | `/workshop/price-governance` | 同上 | GREEN |
| 客户关系 | `workshop-customer.html` | `/workshop/customer` | 同上 | GREEN |

32 张浏览器截图位于 `screenshots/`。最终 1920×1080 原图逐张人工复看；八页 `scrollWidth=clientWidth`、`scrollHeight=clientHeight`、超大 SVG=0、正文开发编号=0、英文行动指令=0。内容页三栏进一步以几何边界核对为 `280 + 992 + 340 = 1612px`，右侧证据栏落在 `x=1580…1920`，没有被业务视口裁切。

## 2. 浏览器组件功能矩阵

| 页面 | 实际点击项 | 结果 |
| --- | --- | --- |
| 日常总控 | 侧栏折叠/展开、任务输入与下达预检、日历/任务流、六数字同事浮层 | 均有可见状态；浮层含专业能力/工作边界且不遮挡底栏；零外部效果 |
| 内容活动 | 三业务视图、生成方案、保存草稿、重新生成、批准并发布 | Tab 可切换；动作先给中文安全预检，不伪造草稿或发布 |
| 统一运营 | 七业务切片、筛选/重读、六类命令入口 | 订单/明细/履约/支付可读；缺数据切片显式等待；命令失败关闭 |
| 达人邀约 | 五阶段、检索/筛选、批次与启动动作 | 阶段可切换；无正式达人数据时保持可信空；不启动外部邀约 |
| 多媒体 | 三内容类型、重读与生产动作 | 三 Tab 均可切换；六轴条件显式；不生成或发布媒体 |
| 经营参谋 | 七分析视图、重读、今日方案 | 七 Tab 均在 1920 视口内；顶部不挤压；原始状态码只在审计折叠区 |
| 价格治理 | 三治理视图、筛选/重读、调价相关动作 | 三 Tab 可切换；正式报价缺失时不显示伪价格；不调价 |
| 客户关系 | 四业务视图、重读、触达预检 | 主投影与补充投影独立失败关闭；四 Tab 可用；不发送触达 |

所有页面的侧栏均实点折叠后出现“展开侧栏”，再展开恢复。最终重载矩阵八页均 `ok=true`，console 未出现页面新增错误。

## 3. 栖月汇真实租户数据追溯

2026-08-29 02:30（Asia/Shanghai）通过本地 API 对 `org-org/dev-project` 做 GET-only 回读：

- 总控：`task-cockpit/v1`，业务任务 `0`；服务端已排除 24 条 `aip.governance / aip.runtime.acceptance / logic_graph_run` 内部记录，分页 `0/false/null`。
- 内容：`content-campaign-view/v1`，3 个固定业务切片，正式项 0。
- 运营：`operations-view/v1`，7 个业务切片、169 条正式来源项；订单 50、订单明细 50、履约 19、支付 50，库存/售后/运营工单按正式来源显式为等待条件或空。
- 达人：`creator-growth-view/v1`，5 个阶段，正式项 0。
- 多媒体：`media-studio-view/v6`，3 个切片，正式项 0。
- 经营参谋：`analyst-view/v2`，7 个视图，正式项 0。
- 价格：`price-governance-view/v2`，3 个视图，正式项 0。
- 客户：`customer-view/v1`，4 个视图，正式项 0；`customer-lifecycle/v1` 与 `customer-contact-governance/v1` 均 HTTP 200，治理 ledger 守恒且外部效果为 0。

Workshop 不直连 `.ssh-db` 中的原始 MySQL；栖月汇事实仅消费现有受治理 P01–P12 / canonical API 投影。空集合与等待条件没有被演示数据或技术任务补齐。

## 4. 根因与修复

1. 客户补充触达投影在 tenant scope 已开启事务后再次执行 `SET TRANSACTION`，导致 HTTP 500；后端移除非法事务顺序，频控使用租户/客户/策略 scoped advisory lock。前端将主权威与补充投影分离，补充失败不再让四视图坍塌。
2. 客户与经营参谋把英文 `requiredAction` 直接显示为经营行动；主业务区改为稳定中文，原始诊断只保留在折叠审计区。
3. 总控前端虽隐藏内部验收任务，API 仍返回 24 条技术记录；服务端 snapshot/page SQL 使用同一业务任务谓词，排除 `aip.*` 与 `logic_graph_run`，正式业务类型和分页语义保持不变。

## 5. 测试与构建

- Web 全量：255 files / 2314 tests GREEN。
- Web TypeScript + Vite production build：GREEN。
- 总控 + 客户后端专项：38 tests GREEN。
- Python `compileall`：GREEN。
- `git diff --check`：GREEN。
- 真实 API 重启后回读：十个主/补充 GET endpoint 均 HTTP 200；总控业务任务 count=0。

已知测试输出中的 React `act()`、React Router future flag、Pydantic `schema` 警告和 Vite chunk-size 提示为既有非失败告警；本切片未新增测试失败、构建失败、数据写入或外部副作用。
