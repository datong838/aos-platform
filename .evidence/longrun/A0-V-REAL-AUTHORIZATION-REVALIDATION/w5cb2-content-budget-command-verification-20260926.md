# W5CB2｜exact 内容预算命令 HELD/PENDING 代码门验证

## 结论

`W5CB2_CONTENT_BUDGET_COMMAND_CODE_GATE_GREEN_REAL_CONTENT_PENDING`。P1 `050a9fa9`、P2a `053bd986`、P2b `d47d5c05`、P2c `f4c20b7d` 和本次 P2d 复审构成代码波。**只证明默认关闭路径具备单次 exact 预算命令交接；未证明当前安装自然执行、Provider 调用、可读产物或经营闭环。**

## 上位方案与实现对账

- 对照 231-5 §4/5/6、231-9 BG-04 及栖月汇数字同事产品方案：审批、预算、能力、来源和安装代次必须在执行前重验；预算 HELD/Journal PENDING 与 Provider 提交分离，未知结果不得重发。产物需真实商品/事实正文，故本波不称完成内容。
- `a0v_104` 在容量 ack 原事务写 pending；claim 最多一次；ack 由数据库要求原代次、同键 HELD＋PENDING＋Runtime Receipt。`dev-org/dev-project` 隔离为零。
- `ContentBudgetCommandOwner` 从当前 Review→Task/Brief→Plan/TaskRun→AgentRun→容量和安装组构造 12 Ref；从唯一批准事件的原 ActionDraft 获取批准额度，按当前数值价格与 Quota 上限算最坏费用；方法 EvidenceBundle 不扩充；调用正式 Host 逐项重验。无批准、价格/来源/容量过期、错代或多义时未 claim。
- claim 后重新预检并只调用一次 capability Host Port；独立事务核验预算 HELD、不可变 Journal PENDING 命令、Runtime Receipt 完整 hash/response/代次，才 ack。Host timeout/读回未知保持 claimed。领域 bundle 与 Host 的命令 payload/hash 合同测试一致，API 无生产 bundle/SDK 导入。
- 修复 Journal `list_held` 原把完整命令 Runtime hash 误比内层 requestHash 的阻断；未放松其他预算或 Receipt 检查。
- `main.py` 新 Worker flag 默认 `false`，显式开仍需同进程 ACTIVE Runtime Host 和 runtime-only DSN；Provider Worker 独立关闭。

## 新鲜验证

- RED→GREEN：Task 创建 Ref 版本冲突、唯一批准原金额、pending selector、Host/bundle 同 hash、缺意图/旧 epoch、单 claim、Host unknown、读回不明、默认关闭 Worker、Journal 完整 hash 各有先失败后修复记录于 P1/P2a/P2b/P2c 文件。
- P2c 合并回归：Owner/容量/AgentRun、公共预算与 Journal 隔离 PostgreSQL **66 passed、7 既有 warnings**；专用 PostgreSQL 容器已停止。`alembic heads=a0v_104`，compileall 与 `git diff --check` 通过。
- 无页面变更，浏览器验收不适用。生产迁移未应用、Worker 未启用、商城源未读、旧 12 Run 未触碰；m1 单写者，无 push。

## 剩余硬门与下一波

1. 当前 full-schema Handoff→Plan/Run→AgentRun→容量→预算完整夹具尚未落地；部分 Owner 成功测试使用受控假权威，隔离 PG 只覆盖各交接/公共预算/Journal 组成段。**生产激活前必须补齐同库一体链**，且核真实安装、审批、数值价格、容量、来源、权限和独立 Receipt；测试绿不等于真实授权。
2. 当前 Owner 要求唯一内容能力，Quota 上界必须被容量覆盖；若合法配置有多能力或较小容量，应以审批/策略修订的 exact 选择解决，不猜能力或 token 分配。该实例保持 pending，不影响下一段默认关闭的核心功能研发。
3. W5CB3 立即接 ProviderRequestReceipt 后唯一外呼、结果 Journal→MeasuredUsage/Budget→可读 Artifact；原 PENDING 不能触发人工评审或反馈终态。随后 W5CB4 接内容 Review/TaskRun 终态与反馈续跑，并补上述生产激活硬门、连续真实自然观察。

结论边界：W5CB2 **代码波完成，业务目标未完成**；不得开启生产或发布。
