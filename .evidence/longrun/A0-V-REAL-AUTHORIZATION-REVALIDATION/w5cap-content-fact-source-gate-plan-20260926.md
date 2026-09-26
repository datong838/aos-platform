# W5cap｜内容生成事实来源门与执行 Owner 复用方案

## 上位方案、现场与目标

复习 231 总控 A1、231-5、231-6 AR2-6/N7、231-9 BG-04 和栖月汇双侧增长产品方案。首链要从批准的方法产生真实可读内容；真实调用须有当前事实、安装代次、审批、容量和预算，未知提交不得重发。W5cao 已使含方法的 approved GrowthPlan 到内部 Task/Brief 可追溯，但 `content.generate` 的 `factSourceRefs` 只做格式/唯一性检查。当前 `ContentGenerateHostService.execute` 仍保留 `FAILED_NO_EFFECT`，而仓库中另有未接入此 Host 的 `ContentExecutionJournal`、`ContentExecutionWorker`、`ContentResultConsumer` 与 exact Provider invoker，不能重新造一套执行 Owner，也不能把隔离测试当自然产出。

本波只关闭**生成前事实来源权威**，不启动 Provider、无新迁移、无共享 DB 写入或商城源读取。含 `salesWeaponMethod` 的 v2 Brief 必须在同一 HostTransaction 以 DB 时钟重新确认当前 Decision→Insight→EvidenceBundle/底层 Evidence、`internal` marking 与七天以内 cutoff；命令 `factSourceRefs` 暂只允许与 approved 方法的 EvidenceBundle exact refs **逐项相等**。额外 Dataset/履行 Receipt 尚未同源证明，先拒绝而不猜测；旧 v1/no-effect 回放不变。此门不证明商品事实本身已经语义核验，也不授予真实调用。

## 文件级步骤和验证

1. `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py` 先 RED：v2 合法 exact 来源通过；缺项、替换 hash、额外 `DataFulfillmentReceipt`、过期/撤销/越权来源均在预算前拒绝；v1 保持历史路径。必要时增加隔离 PG 测试验证原 `require_growth_plan_sources` Owner 读回。
2. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 最小改动：在 v2 的当前 Plan/Brief 核对后，通过原 `require_growth_plan_sources` 以 `markings=['internal']`、DB checked_at 与 Plan method cutoff 的七天界重读；比较 current Decision exact Ref、Insight cutoff、方法 evidence exact 集合与命令 fact ref 的顺序。严禁另开连接、跳过原审批门或在失败时留下 hold。
3. 专项、相邻累计回归、编译、diff check；无 UI 改动，浏览器 N/A。复审 v1 兼容、同租户与同事务、失败前无副作用、方法来源未变成商品语义背书。
4. verification 落盘→m1 精确提交→D-waves 与 AOS/Prime 上下文更新。下一波 W5caq 检查现有 Journal/Worker/Consumer/Invoker 的正式 Host 接线与缺口，先让持久入队、提交后唯一外呼、结果读回和 UNKNOWN 对账形成单链；无 current approval/Provider 许可时只做隔离技术验证，不尝试真实调用。

停止条件：若原来源 reader 不能在同一事务以明确 marking 证明 v2 来源，停止本波实现并记录缺口；未知 Provider 边界/Receipt 一律冻结、不重发。旧 12 Run 后置，230 L0 挂起，dev-org 仅零 canary，m1 单写不 push。
