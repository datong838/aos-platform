# Workshop 安装目录 / 业务读模型上下文分层与标题层级验收

- 时间：2026-08-29 05:33～05:36 Asia/Shanghai
- 租户：`org-org/dev-project`
- API owner：PID `34859`，`127.0.0.1:8080`
- 边界：只调整 Web 语义与标题层级；未修改安装目录、业务数据、SourceReadiness、Pipeline、Provider 或发布状态。

## 方案与实现

- 方案：`119-BI-W0经营参谋生意探究全量开发清单与波次实施计划.md` 第 111 节。
- `EcommerceWorkshopShell.tsx` 将泛化的“模块与数据上下文 / 数据截止 / 状态”收窄为“模块安装上下文 / 安装目录截止 / 模块能力”，明确业务页继续消费各自 canonical GET。
- 价格治理、客户关系和经营参谋由 AppShell 专用视觉页头独占一级标题；共享 Module Shell 不再生成重复 `h1`。
- `AppShell.workshop.test.tsx` 为每个路由安装真实匹配的 `moduleId/route`，不再用“未安装页”替代页面测试。

## 专项与累计回归

- Shell / Host / AppShell 专项：`3 files / 23 tests passed`。
- Web 累计：`255 files / 2314 tests passed`。
- TypeScript + production build：`359 modules transformed`，构建成功；仅保留既有大 chunk 提示。

## 内置浏览器逐页复验

逐一重新打开下列实际运行页并读取 DOM；八页均满足：真实 `data-module-id` 匹配、一级标题恰好 1 个、横向溢出 0、旧“模块与数据上下文”不可见、新“模块安装上下文”存在。

| 路由 | moduleId | h1 | 可见按钮数 | 横向溢出 |
|---|---|---:|---:|---:|
| `/workshop/cockpit` | `ecommerce.task-cockpit` | 1 | 21 | 0 |
| `/workshop/content-campaign` | `ecommerce.content-campaign` | 1 | 26 | 0 |
| `/workshop/operations` | `ecommerce.operations` | 1 | 29 | 0 |
| `/workshop/creator-growth` | `ecommerce.creator-growth` | 1 | 30 | 0 |
| `/workshop/media-studio` | `ecommerce.media-studio` | 1 | 18 | 0 |
| `/workshop/analyst` | `ecommerce.analyst` | 1 | 14 | 0 |
| `/workshop/price-governance` | `ecommerce.price-governance` | 1 | 18 | 0 |
| `/workshop/customer` | `ecommerce.customer` | 1 | 19 | 0 |

本轮与同一连续验收 turn 的前置点击结果合并：八页侧栏折叠/展开、主 Tab、重读、详情/浮层及页头动作均已实际点击；缺少可提交业务条件的动作返回中文安全预检，未产生外部效果。客户关系 1280×720 首屏另做可见复核，页头、状态条、三栏骨架与底部重读入口均未遮挡。

## 结论

本切片为 `CODE_TEST_BROWSER_GREEN`。它证明安装目录和当前业务读模型语义不再混淆、页面标题层级唯一、八页实际路由重新验收；不等于 SourceReadiness、真实试点或发布 GREEN。继续等待自然调度事实，并串行进入下一工程/数据验收切片。
