# Workshop 目录依赖权威与八菜单浏览器验收

- 日期：2026-08-29
- 租户：`org-org/dev-project`
- 分支：`m1`
- 代码提交：`4d2072a4`
- 范围：目录 AIP FeatureActivation exact reader；八个正式菜单入口的视觉、侧栏、页签、重新读取与安全预检。

## 代码与数据边界

- 新增同租户 AIP FeatureActivation revision/hash 权威读取；表不存在、记录过期或读取异常时返回可信空。
- 新增迁移只形成待审批施工包，本次没有对真实数据库执行迁移，也没有写入激活记录。
- 目录不得以 Bundle 声明、测试通过或数据库表存在推断 AIP 功能已激活。

## 专项与累计回归

- Workshop/API 定向累计：`247 passed`。
- Alembic 唯一 head：`wcat_001 (head)`。
- `git diff --check`：通过。

## 内置浏览器逐页验收

| 正式入口 | 标题与主内容 | 侧栏折叠/恢复 | 业务组件点击 | 安全操作入口 |
|---|---|---|---|---|
| `/workshop/cockpit` | 通过 | 通过 | 打开并关闭“导购顾问”介绍浮层，专业能力与工作边界可见 | “下达”在空输入下返回安全提示 |
| `/workshop/content-campaign` | 通过 | 通过 | 切换“内容日历” | “新建活动”返回不写业务数据的预检提示 |
| `/workshop/operations` | 通过 | 通过 | 重新读取正式运营视图 | “新建处理”返回安全预检提示 |
| `/workshop/creator-growth` | 通过 | 通过 | 切换“招募漏斗” | “新建邀约批次”返回安全预检提示 |
| `/workshop/media-studio` | 通过 | 通过 | “短视频”页签成为 selected/tabpanel | “新建内容任务”返回安全预检提示 |
| `/workshop/analyst` | 通过 | 通过 | “数据质量”页签成为 selected/tabpanel | “查看今日方案”准确切换到“增长计划” |
| `/workshop/price-governance` | 通过 | 通过 | “竞品比价”页签成为 selected/tabpanel | “新建监测策略”返回安全预检提示 |
| `/workshop/customer` | 通过 | 通过 | “生命周期旅程”页签成为 selected/tabpanel | “新建触达任务”返回安全预检提示 |

八页均未出现 `字段漂移`、`TypeError`、`页面加载失败` 或 `Failed to fetch`。达人、媒体、价格的正式路由分别是 `creator-growth`、`media-studio`、`price-governance`；旧短别名不作为产品入口或验收证据。

## 截图

- `cockpit-canonical.png`
- `content-campaign-canonical.png`
- `operations-canonical.png`
- `creator-growth-canonical.png`
- `media-studio-canonical.png`
- `analyst-canonical.png`
- `price-governance-canonical.png`
- `customer-canonical.png`

截图由内置浏览器在本地正式入口、当前 API 服务和当前租户上下文下生成；可信空、待核对与等待条件保持显式，没有填充演示业务事实。
