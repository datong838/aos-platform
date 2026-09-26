# W5CB2-P2｜exact 内容预算命令 Owner（施工前）

## 上位复习与 P1 现场

- 承接 231-5 的审批、预算、容量、来源与默认禁入，231-9 的内容首链；产品目标是可读草稿而非测试绿。P1 `050a9fa9` 只证明容量→预算意图原事务交接、单次 claim、严格 ack 和 Task 创建 Ref 合同；没有自然命令提交、Provider 或 Artifact。
- 正式包内路径为 `ContentCapabilityRequest`→`execute_content_capability`→`LockedEcommerceGrowthHostPort.commit`。复核发现 `ecommerce_growth` 是可插拔 bundle，AOS API 环境不直接安装该 Python 包；Host Owner 不能从源码路径导入 bundle，否则破坏可插拔隔离。因此 Host Owner 构造同一严格命令 envelope，复用 `ContentGenerateHostService._strict_content_generate_command` 的唯一校验与正式 capability Host Port；bundle 自身路径保留原生请求/回执合同，并在集成测试比较两侧同一命令 hash/Receipt。Host 在锁内做 12 类 exact authority/事实来源/费用重验。Owner 只取权威来源并控制单次交接，不复制一套宽松业务判定。
- 旧 12 Run 和商城源读不在本波；dev-org 仅零 canary。所有 Worker 默认关闭，生产迁移和真实安装启用仍需独立验收。

## 文件级清单与 RED

1. `services/aos-api/aos_api/ecommerce_content_budget_command_owner.py`：为 P1 纯价格边界添加只读预检。按 reviewKey 精确锁定预算意图、Review Receipt、TaskBrief、Plan/TaskRun、AgentRun、容量 reservation、安装 group；使用原 Handoff 的 Task 创建 Ref。解析当前 Route/Policy/Budget/Price/ActionApprovalEvent，额度只能来自原 approved ActionDraft；解析 sales_weapon_method 的事实来源。任何缺失、多义、过期、epoch 漂移或价格不可数值计费直接禁入，不 claim。
2. 同文件：构造与包内 `ContentCapabilityRequest.command_payload()` 完全同形且 hash 相同的命令，经 Host 严格解析/revalidate 后调用 `a0v_104` claim 一次，并单次走正式 capability Host Port。Host 未明确返回、提交后读回不完整、租户/Ref/代次不等时保持 claimed/unknown，绝不换键重发；不得从 AOS API 直接导入 bundle 源码。
3. 同文件：独立新事务读 HELD 预算、PENDING Journal、Runtime Receipt 的 exact 键/hash/安装代次，通过后执行 `a0v_104` ack，并再次独立读 accepted；仅返回 `CONTENT_BUDGET_PENDING`，不得称已生成文案。
4. `services/aos-api/aos_api/main.py`：仅在 Runtime Host ACTIVE、runtime-only 身份、当前 Dispatch/安装可证时可选启动该 Owner；默认关闭，Provider Worker 独立保持关闭。
5. `services/aos-api/tests/extension_runtime/test_ecommerce_content_budget_command_owner.py` 及 PG 邻近测试：先 RED 验批准额度不足、未知价格、无审批、来源过期、旧 epoch、容量到期、并发 claim、同键重入、Host unknown、跨租户及 dev-org 零结果；再最小实现。补完整同库 Handoff→容量→预算交接夹具。

## 验证与退出

- 专项、预算/Host/Journal 累计回归，适用时浏览器验收；核对产品/技术方案的一致性。verification 落盘后才可称 W5CB2 完成并提交 m1，再同步 D-waves/AOS/Prime，进入 W5CB3 Provider/MeasuredUsage/Artifact。
- 无可用批准额度或事实来源只阻断该实例，改做主线代码与测试；但不能造 Ref、手动运行、接受未知结果或激活生产 Worker。
