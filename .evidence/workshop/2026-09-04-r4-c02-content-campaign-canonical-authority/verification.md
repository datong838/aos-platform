# WORKSHOP R4-C02 验证记录

- 任务：`WORKSHOP-R4-C02-CONTENT-CAMPAIGN-CANONICAL-AUTHORITY`
- 验证时间：2026-09-04 16:18（Asia/Shanghai）
- 真实租户：`org-org/dev-project`
- 负向隔离租户：`dev-org/dev-project`
- 边界：只读 GET、无迁移执行、无真实活动/内容写入、无外部发布。

## 实现结论

1. 内容与活动页面的计划、日历、主内容和变体改为一次只读 repeatable-read 数据库连接内读取，页面只生成一个 timezone-aware cutoff。
2. 三个业务切片保留 savepoint 级失败隔离；单切片读取失败不会污染同一截止面的其他切片。
3. `ContentVariant` 只查询当前 `MasterContentIntent.masterArtifactRef` 精确引用的 `variant_of` 关系；租户内无关变体不再把可信空主内容误判为阻断。
4. 相关变体仍校验主/变体 artifact 当前哈希、关系类型、唯一 Receipt 和唯一 MasterContentIntent 匹配，任何漂移均失败关闭。

## 专项与累计回归

- 合同、Store、页面组合和迁移静态专项：34/34 通过。
- 加入 Workshop API 累计回归：39/39 通过。
- Content Campaign Web 客户端与页面：2 文件、6/6 通过。
- Python 编译检查：通过。
- `git diff --check`：通过。
- 首次重启后测试的 32 个 setup error 均由 Docker/PostgreSQL 未启动导致；恢复本地开发 PostgreSQL 后原样重跑通过，未将环境失败记为代码结论。

## 真实数据与租户隔离探针

- `GET /v1/ecommerce-workshop/views/content-campaign`
  - `org-org/dev-project`：HTTP 200。
  - `evaluatedAt == dataCutoff == 2026-09-04T08:10:18.885736Z`。
  - `plan`：`ready`，eligible 0，blocker 0。
  - `calendar`：`ready`，eligible 0，blocker 0。
  - `content`：`ready`，eligible 0，blocker 0。
- 同一路由 `dev-org/dev-project`：HTTP 404，`NOT_FOUND / Workshop module is not installed`。
- 结论：当前真实租户在该 authority 上是可工作的可信空集合；未用开发编号、演示活动或隔离租户数据填充。

## 内置浏览器验收

- 页面：`http://127.0.0.1:5173/workshop/content-campaign`。
- 已验证“活动策划 / 内容日历 / 日常模板”三页签均可切换，且三者分别显示正式可读、0/0 的可信空状态。
- 已验证“读取正式活动计划”会自动回填中央活动意图输入框。
- 已验证“生成方案”返回本地安全预检提示，明确未创建业务记录、生成任务或外部发布。
- 已验证左侧平台导航折叠及展开恢复，八个电商工作台菜单仍完整可见且可滚动。
- 页面控制台 error 0；仅有 2 条既有 React Router v7 future-flag warning。
- 1280×720 当前首屏未出现放大镜大图标、底部遮挡中央/右侧栏或浮层覆盖主要工作区。

## 方案一致性与风险复审

- 与 R4-C02 文件级施工包一致：单 cutoff、单 snapshot、租户绑定、精确版本/哈希/Receipt、可信空、切片失败隔离均已覆盖。
- 保持 GET-only；本波未执行迁移、外部 Provider、发布、发送、退款、发货、调价或客户触达。
- `ready + 0` 只代表当前截止面的正式读取成功，不代表已有活动内容或获得发布授权。
