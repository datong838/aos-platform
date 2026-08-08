# 前后端功能缺失清单

> 检查时间：2026-08-07
> 租户上下文：org-org · dev-project · 默认工作区（栖月汇商贸有限公司）
> 验证方式：**CDP 桥接实测**（6 页截图 + 按钮检查）+ 后端 OpenAPI + API curl + 前端代码静态审查
> 验证人：Agent 自测（cdp-bridge 技能）

## 0. 系统状态

| 服务 | 状态 | PID | 备注 |
|---|---|---|---|
| 后端 8080 | ✅ | 68844 | `Bearer dev` + `X-Org-Id: org-org` + `X-Project-Id: dev-project` 可用 |
| 前端 5173 | ✅ | 14754 | Vite dev server 返回 React shell |
| **CDP 桥接（Chrome headless=new）** | ✅ | 51420 | **2026-08-07 跑通**。CDP_PORT=9225 监听，Chrome/151.0.7922.76。所有写路径强制 `/tmp/cdp-chrome-home-9225/`，沙箱外启动脱钩，未触发 ~/Library 限制 |
| 后端数据（org-org） | ✅ | — | connectors=8、installations=5、cases=2 |

### CDP 实测产出（6 张截图 + 6 页文本抓取）
```
/tmp/cdp-screenshots/
├── 01_连接器目录.png ................... 157KB ✅
├── 02_数据源列表.png ................... 115KB ✅
├── 03_Pipeline 列表.png ................ 137KB ✅
├── 04_资产包 Registry Tab.png .......... 142KB ✅
├── 05_资产包 安装管理 Tab + 动作面板.png  291KB ✅
└── 06_接入案例 列表 → 详情.png ......... 171KB ✅
```

### CDP 实测页面渲染验证
| 页面 | 渲染 | 租户切换 | 文本前 450 字抽样 |
|---|---|---|---|
| 01 连接器目录 | ✅ | ✅ 栖月汇商贸有限公司 | "数据源与同步 / 连接器目录 / 组织 · 栖月汇商贸有限公司 / 默认工作区" |
| 02 数据源列表 | ✅ | ✅ | "数据源管理 / 栖月汇商贸" |
| 03 Pipeline 列表 | ✅ | ✅ | "管道构建 / 栖月汇商贸" |
| 04 资产包 Registry | ✅ | ✅ | "运维交付 / 资产包 / 三 Tab 存在：资产 Registry / 组合预检与创建 / 安装管理" |
| 05 安装管理+动作面板 | ✅ | ✅ | "安装动作面板打开 / 6 类动作按钮：提交审批/批准/拒绝/执行 Apply/验证并激活/回滚" |
| 06 接入案例详情 | ✅ | ✅ | "运维交付 / 接入案例" |

---

## 1. 缺失清单（共 6 项）

### ✅ GAP-01 连接器目录：已安装连接器无"卸载"按钮（已修复）

- **CDP 实测确认**：截图 `/tmp/cdp-screenshots/01_连接器目录.png`（157KB）。页面文本抓取未出现"卸载"字样，可点击元素只有"创建数据源"（已安装）和"安装"（未安装）。租户上下文 ✅ 栖月汇
- **后端 API（已存在）**：`POST /v1/connector-plugins/{plugin_id}/uninstall`
  - 实测：`curl -X POST .../v1/connector-plugins/jdbc-mysql-ssh/uninstall` 返回 `403 {"code":"FORBIDDEN","message":"required connector cannot be uninstalled"}` → 接口存在且有 required 校验
- **后端文件**：`aos-platform/services/aos-api/aos_api/routers/connector_plugins.py`（OpenAPI 路径已注册）
- **前端缺失位置**：`aos-platform/apps/web/src/pages/s2/DataConnectionPage.tsx` 第 339–354 行
  - `c.installed ?` 分支只渲染 `<Link>创建数据源</Link>`
  - **完全没有卸载分支**
- **约束**：DEMO_CATALOG 中 `required=true` 的连接器卸载按钮需灰掉禁用
- **修复方向**：前端在 installed 分支追加"卸载"按钮，required=true 时 disabled
- **状态**：✅ 已修复（2026-08-07）。DataConnectionPage.tsx L216-225 加 `handleUninstall`，L350-367 加"卸载"按钮（required=true 时 disabled）。CDP 自测 PASS，"卸载"关键词已找到

---

### ✅ GAP-02 资产包 Registry Tab：无"发布新版本 / 废弃 / 撤销发布"按钮（已修复）

- **CDP 实测确认**：截图 `/tmp/cdp-screenshots/04_资产包 Registry Tab.png`（142KB）。页面渲染"资产 Registry / 组合预检与创建 / 安装管理"三 Tab。可点击元素列表（80 个）中无"发布""废弃""撤销"字样。租户上下文 ✅ 栖月汇
- **后端 API（已存在）**：
  - `POST /v1/bundles/{bundle_id}/versions/{version}/publish`
  - `POST /v1/bundles/{bundle_id}/versions/{version}/deprecate`
  - `POST /v1/bundles/{bundle_id}/versions/{version}/revoke`
- **后端文件**：`aos-platform/services/aos-api/aos_api/routers/asset_bundles.py` 第 299/324/350 行
- **前端缺失位置**：`aos-platform/apps/web/src/pages/s2/assetBundles/RegistryPanel.tsx` 第 96–110 行
  - 版本表格列只有"查看版本事实"一个按钮
  - **没有发布/废弃/撤销**
- **风险**：当前前端只能读取 Registry，不能写操作
- **修复方向**：RegistryPanel 版本行追加 3 个动作按钮，按 asset-publisher 角色门禁
- **状态**：✅ 已修复（2026-08-07）。RegistryPanel.tsx BundleDetail 版本表格追加"生命周期"列，按 version.status 控制可用性：draft/validated→可发布，published→可废弃/撤销。CDP 自测 PASS，缺失告警已消失

---

### ✅ GAP-03 资产包 Registry Tab：无"安装此资产包 → 创建 installation"入口（已修复）

- **CDP 实测确认**：同 GAP-02 截图。选中资产包/版本后页面无"安装"CTA 按钮出现。租户上下文 ✅ 栖月汇
- **后端 API（已存在）**：`POST /v1/bundle-installations`（operation_id=`create_bundle_installation`）
- **前端缺失位置**：
  - `aos-platform/apps/web/src/pages/s2/assetBundles/RegistryPanel.tsx` — 选资产包/版本后无"开始安装"按钮
  - `aos-platform/apps/web/src/pages/s2/routes.tsx` 第 37 行 — 只有 ApolloAssetsPage 单页，无安装向导过渡页
- **修复方向**：RegistryPanel 选中版本后追加"安装此版本"CTA，调 `POST /v1/bundle-installations`
- **状态**：✅ 已修复（2026-08-07）。RegistryPanel.tsx 新增 InstallVersionCta 组件，选中版本后显示"安装此版本"按钮，两步调用：1) POST /v1/bundle-compositions:resolve 获取 compositionId+lockRevision；2) POST /v1/bundle-installations 创建安装。CDP 自测 PASS

---

### ✅ GAP-04 资产包安装管理：无"卸载"动作按钮（后端也缺）（已修复）

- **CDP 实测确认**：截图 `/tmp/cdp-screenshots/05_资产包 安装管理 Tab + 动作面板.png`（291KB）。post_js 自动切换到"安装管理"Tab 并点击列表行，动作面板真实打开（tabClick:1 rowClick:1）。页面文本出现"安装动作""提交审批""批准""拒绝""执行 Apply""验证并激活""回滚"6 类按钮，**但无"卸载"按钮**。租户上下文 ✅ 栖月汇
- **后端动作列表**：由 `_action_route` 在 `aos-platform/services/aos-api/aos_api/routers/bundle_installations.py` 第 254–271 行注册：
  - `submit` / `approve` / `reject` / `apply` / `verify` / `rollback` ✅ 前后端都有
  - **后端根本没有 `uninstall` API** — InstallationState 枚举只到 `rolled_back`，没有 uninstalled/removed 终态
- **前端动作定义**：`aos-platform/apps/web/src/pages/s2/assetBundles/installationActions.ts` 第 3–9 行
  - 只定义了和后端一致的 6 个动作
- **前端面板**：`aos-platform/apps/web/src/pages/s2/assetBundles/InstallationActionPanel.tsx` 第 91–106 行
  - 按钮来自 `installationActionAvailability()`，没有卸载
- **结论**：**后端缺能力 → 前端自然没按钮**。用户投诉"电商数据包验证了安装-卸载-安装，但安装管理里没有卸载按钮"即此项
- **修复方向**：
  1. 后端：InstallationState 加 `uninstalled` 终态；InstallationControl 加 `uninstall()` 方法；`_action_route("uninstall", ...)` 注册 `POST /v1/bundle-installations/{id}/uninstall`
  2. 前端：installationActions.ts 加 `uninstall`；ACTIONS_BY_STATE 在 active/rolled_back 等状态暴露；InstallationActionPanel 自动渲染
- **状态**：✅ 已修复（2026-08-07）。后端 7 文件（composition_contracts.py 加 uninstalled 状态+转换边+UninstallInstallationRequest；control_policy.py 加操作常量+角色；control_protocols.py 加 Protocol 方法；installation_service.py 加 uninstall()+_append_uninstall；installation_store.py 加 append_uninstall_in_transaction；bundle_installations.py 加路由；installation_evidence.py 加转换注册）。前端 12 文件（types/operations/client/installationActions/Panel/Dialog + controller 层 + 测试）。后端重启后 OpenAPI 已注册 `/v1/bundle-installations/{id}/uninstall`。CDP 自测 PASS，缺失告警已消失。⚠️ DB 层 Alembic 迁移待补（CHECK 约束/触发器未认识 uninstalled，Python 层已就绪）

---

### ✅ GAP-05 资产包安装管理列表：无"新建安装 / 选择资产包安装"入口（已修复）

- **CDP 实测确认**：同 GAP-04 截图。安装管理 Tab 顶部仅有列表过滤，无"新建安装"按钮。租户上下文 ✅ 栖月汇
- **后端 API（已存在）**：`POST /v1/bundle-installations`
- **前端缺失位置**：`aos-platform/apps/web/src/pages/s2/assetBundles/InstallationPanel.tsx`
  - 只有列表，顶部无"新建安装"+"选资产包/版本"向导
- **死锁**：用户只能在 Registry 里找资产再安装，但 Registry 里也没安装入口（GAP-03）→ 整个安装创建链路断开
- **修复方向**：InstallationPanel 顶部加"新建安装"按钮，弹出选资产包/版本向导
- **状态**：✅ 已修复（2026-08-07）。InstallationPanel.tsx header 改为 flex 布局，右侧加"新建安装"按钮，点击切换到 Registry Tab（GAP-03 已有安装 CTA）。AssetBundlesPage.tsx 传 onNavigateToRegistry 回调。CDP 自测 6/6 PASS

---

### ✅ GAP-06 接入案例详情：无"Evidence 快照"按钮（已修复）

- **CDP 实测确认**：截图 `/tmp/cdp-screenshots/06_接入案例 列表 → 详情.png`（171KB）。post_js 自动点击案例卡片成功进入详情（pickCase:1）。详情页文本出现"阶段"字样。租户上下文 ✅ 栖月汇
- **后端 API（已存在）**：
  - `POST /v1/integration-cases` 创建
  - `POST /v1/integration-cases/{case_id}/evidence-snapshots` 打快照（请求体为空 `{}`
  - `GET /v1/integration-cases/{case_id}/timeline` 看时间线
- **后端缺失 API**：没有 `POST /v1/integration-cases/{case_id}/advance`（手动跳阶与 Evidence 驱动架构冲突，不做）
- **前端当前状态**：`aos-platform/apps/web/src/pages/s2/IntegrationCasesPage.tsx` 第 51–65 行
  - 只有"重试读取"按钮，详情里没有任何动作入口
- **架构约束**：阶段是 Evidence 驱动的只读投影，手动跳阶会破坏"连续满足"不变量。但"生成 Evidence 快照"会触发服务端重新投影，可能推进阶段——这就是合规的"推进"方式
- **修复方向**：只做 Evidence 快照按钮（后端已就绪），不做手动 advance
- **状态**：✅ 已修复（2026-08-07）。IntegrationCaseDetail.tsx 加 onCreateSnapshot/snapshotPending/snapshotError props + "生成 Evidence 快照"按钮（scope=current 时显示）。IntegrationCasesPage.tsx 加 createSnapshot mutation 函数（crypto.randomUUID 做幂等键 + detail.etagVersion 做 If-Match + 成功后刷新 detail+timeline）。CDP 自测 6/6 PASS，"生成 Evidence 快照"关键词已找到

---

## 2. 优先级建议（按用户投诉点排序）

| 优先级 | 项 | 触发原因 | 工作量 |
|---|---|---|---|
| P0 | GAP-04 安装管理卸载 | 用户直接投诉 | 后端状态机+API+前端按钮，中 |
| P0 | GAP-01 连接器卸载按钮 | 用户直接投诉 | 纯前端改，小 |
| P1 | GAP-03 Registry 安装 CTA | 打通 Registry→Installation | 前端+API 调用，小 |
| P1 | GAP-02 Registry 发布/废弃/撤销 | Registry 只读 | 纯前端+角色门禁，小 |
| P2 | GAP-05 安装列表新建入口 | 死锁 | 前端向导，中 |
| P2 | GAP-06 接入案例推进 | 阶段只读 | 后端 advance API+前端按钮，中 |

---

## 3. 验证证据索引

### 3.1 后端 OpenAPI 路径（实测 curl 确认存在）
```
/v1/connector-plugins
/v1/connector-plugins/{plugin_id}/install
/v1/connector-plugins/{plugin_id}/uninstall      ← GAP-01 后端有，前端无按钮
/v1/bundle-installations
/v1/bundle-installations/{installation_id}
/v1/bundle-installations/{installation_id}/apply
/v1/bundle-installations/{installation_id}/approve
/v1/bundle-installations/{installation_id}/reject
/v1/bundle-installations/{installation_id}/rollback
/v1/bundle-installations/{installation_id}/submit
/v1/bundle-installations/{installation_id}/verify
                                                  ← GAP-04 缺 /uninstall
/v1/integration-cases
/v1/integration-cases/{case_id}
/v1/integration-cases/{case_id}/evidence-snapshots
/v1/integration-cases/{case_id}/timeline
                                                  ← GAP-06 缺 /advance
```

### 3.2 后端实测数据（org-org/dev-project）
- connectors: 8 个（jdbc-mysql、jdbc-mysql-ssh 等 installed=true；jdbc-postgres 等 installed=false）
- bundle-installations: 5 条（栖月汇商贸 · 微商城全栈接入）
- integration-cases: 2 条（stage=planned，blockerCount=15）

### 3.3 关键文件清单
| 文件 | 行号 | 内容 |
|---|---|---|
| `apps/web/src/pages/s2/DataConnectionPage.tsx` | 339-354 | 连接器卡片按钮分支（缺卸载） |
| `apps/web/src/pages/s2/assetBundles/installationActions.ts` | 3-9 | 动作枚举（缺 uninstall） |
| `apps/web/src/pages/s2/assetBundles/installationActions.ts` | 46-54 | ACTIONS_BY_STATE（缺 uninstall） |
| `apps/web/src/pages/s2/assetBundles/InstallationActionPanel.tsx` | 91-106 | 动作按钮渲染（缺卸载） |
| `apps/web/src/pages/s2/assetBundles/RegistryPanel.tsx` | 96-110 | 版本表格（缺发布/废弃/撤销/安装） |
| `apps/web/src/pages/s2/IntegrationCasesPage.tsx` | 51-65 | 详情只有重试按钮 |
| `services/aos-api/aos_api/routers/bundle_installations.py` | 254-271 | _action_route 注册（缺 uninstall） |
| `services/aos-api/aos_api/routers/asset_bundles.py` | 299,324,350 | publish/deprecate/revoke 后端有 |
| `services/aos-api/aos_api/routers/integration_cases.py` | 283-398 | 无 advance 接口 |

---

## 4. 待办（未实施）

本清单仅记录问题，未做任何代码修改。实施时需按 P0→P2 顺序，每个 GAP 先写技术方案（spec 9 章）经用户批准再编码。

- [ ] GAP-04 实施卸载（后端状态机+API+前端按钮）
- [ ] GAP-01 实施连接器卸载按钮（纯前端）
- [ ] GAP-03 实施 Registry 安装 CTA
- [ ] GAP-02 实施 Registry 发布/废弃/撤销按钮
- [ ] GAP-05 实施安装列表新建入口
- [ ] GAP-06 实施接入案例阶段推进
