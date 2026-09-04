# R4-C04 内容与活动风险决策验证

- 截止：2026-09-04T18:03:00+08:00
- 正向租户：`org-org/dev-project`（栖月汇微商城）
- 负向租户：`dev-org/dev-project`
- 任务：`WORKSHOP-R4-C04-CONTENT-CAMPAIGN-RISK-DECISION`

## 业务闭环

- 折扣与毛利边界、库存与供给边界均可录入中文经营约束并选择采纳建议、保持当前方案或暂缓决策。
- 决策以 exact `TaskBriefRevision`、`expectedVersion` 和内容哈希执行 CAS；结果写入 successor revision 并返回 canonical Receipt。
- 撤销读取上一 revision 的业务输入并创建新的 successor，不更新或删除历史版本。
- 页面不复制视觉稿中的折扣、金额、毛利或库存数字；所有建议与约束均由运营人员显式确认。

## 自动化验证

- API 风险工作流专项：6/6。
- API 内容活动累计：44/44。
- Web 页面与宿主专项：11/11。
- Web 全量累计：271 文件、2440 测试全部通过。
- TypeScript 与生产构建：通过。

## 内置浏览器与真实租户验证

页面：`http://127.0.0.1:5173/workshop/content-campaign`

1. 重启 8080 API 后健康检查通过，栖月汇真实数据 SSH 隧道就绪。
2. 点击“读取正式活动计划”并生成内部活动草稿第 1 版，Receipt `w2r-7ac45c013ddb472e84ed`。
3. 点击折扣与毛利“采纳建议并重算”，形成第 2 版，Receipt `w2r-26364223552642539823`。
4. 点击库存与供给“保持当前方案”，形成第 3 版，Receipt `w2r-9db3900e8659401a8f81`。
5. 点击“撤销最近一次风险决策”，形成第 4 版，Receipt `w2r-b96b51eb3b164f1d8e83`。
6. 页面活动列表、中央底栏、右侧风险栏同步显示第 4 版；库存决策已撤销，折扣决策仍显示其来源第 1 版。
7. 左侧八个电商工作台菜单完整，侧栏折叠按钮存在；页面无巨型放大镜或顶部遮挡。

## 数据回读与隔离

- Brief：`brief-d741d19300b641499ddd`；Task：`task-ded757b12d9f47fc87c5`。
- revision 1：生成草稿；revision 2：写入折扣/毛利决策；revision 3：追加库存/供给决策；revision 4：撤销 revision 3 并保留 revision 2 的折扣决策。
- 四个 revision 均有不同内容哈希并可回读。
- `org-org/dev-project` 对该 Brief 可见 4 行；`dev-org/dev-project` 为 0 行。
- Provider、Approval、TaskRun、外部发布和外部业务变更计数均为 0。

结论：`WORKSHOP_R4_C04_CONTENT_CAMPAIGN_RISK_DECISION_GREEN`。下一项自动进入 `R4-C05`。
