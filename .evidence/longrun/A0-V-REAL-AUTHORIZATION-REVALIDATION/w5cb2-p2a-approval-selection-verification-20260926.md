# W5CB2-P2a｜唯一批准事件与当前待办选择阶段验证

- 基线 `c84c63e8`；本阶段仍属于 W5CB2-P2，不代表预算命令 Owner 完成。保留 m1 单写者、默认关闭、无生产迁移/Provider/商城源读。
- 方案复审发现 bundle 的 `ecommerce_growth` Python 包并未安装于 API 进程。为守可插拔边界，修正 P2 方案：Host Owner 构造经 `ContentGenerateHostService` 唯一严格解析的同形命令；包内 `ContentCapabilityRequest/execute_content_capability` 不移入 Host，后续做 hash/Receipt 合同对照。
- `ContentBudgetCommandOwner.list_pending` 只取租户内、pending/attempt=0、`a0v_104` current 为真的有界集合，最多 16。旧代/过期容量不会进入候选。
- `_approved_action` 从当前任务、`ecommerce_growth_content_generate` 唯一 approved ActionApprovalEvent 查询原 ActionDraft 正数分位上界；无事件、多事件、额度缺失/零/布尔、过期立即禁入。使用公共 `AipBudgetReservationStore._approval_authority` 再验原 Task/operation/action binding/金额及 immutable hash；不复制审批判定或编造金额。
- RED：新审批唯一性测试先因 helper 缺失失败；新 selector 测试先因 Owner 无 scoped connector 失败。GREEN：本文件 3/3；`compileall` 与 `git diff --check` 通过。浏览器不适用（无页面变更）。
- 未完成：正式命令 12 Ref 解析、价格/配额联动、同 hash 对照、单次 claim/Host commit、独立 HELD+PENDING+Receipt ack、Worker 默认关闭接线、同库一体夹具、累计回归。不能声称内容已经生成或预算已经预留。
- 下一阶段 W5CB2-P2b：构造完整 exact 命令并在 claim 前用 Host revalidate；随后一次 Host commit 与提交后对账。P2 完整 verification 和 AOS/Prime 更新仍未达到退出门。
