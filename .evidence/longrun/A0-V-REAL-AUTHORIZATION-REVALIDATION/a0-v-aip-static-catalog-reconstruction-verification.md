# A0-V AIP 静态目录隔离重建验证

## 1. 结果

`A0V_AIP_STATIC_CATALOG_RECONSTRUCTION_GREEN`。

在 `127.0.0.1:18435/aos_meta_head` 隔离恢复克隆中，canonical ecommerce-growth publisher 已幂等重建 6 个 Agent、37 个 Skill、10 个 Capability 静态定义。没有创建租户 AgentInstance、SkillBinding、CapabilityBinding 或 runnable/available 状态。

## 2. 执行与证据

- 输入：当前仓库 `bundles/solutions/ecommerce-growth`；
- 入口：`services/aos-api/scripts/publish_ecommerce_growth_aip.py`；
- 两次已验证 replay 结果完全一致：`agentCount=6`、`skillCount=37`、`capabilityCount=10`；
- 仓库外执行记录：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260910/logs/a0v-aip-static-catalog-publication.json`；
- 记录 SHA-256：`6f652848f26e749ad24eb721b0a8f1277e073f29343386f6159df52db1aa432f`。

首次 publisher 进程返回 0 后，证据包装器因 stdout 含初始化日志而不能按“单一 JSON”解析；该包装器没有生成证据文件。随后改为从末尾识别结构化结果并执行两次幂等重放，结果一致。该问题只发生在证据包装层，没有修改 publisher 或重试非幂等动作。

## 3. API 回读

正向 `org-org/dev-project` 与 canary `dev-org/dev-project` 均返回：

- Agent registry：definition=6、skillDefinition=37、capabilityDefinition=10；
- installed=0、runnable=0；
- Capability catalog：count=10、availableCount=0；
- capabilityBindingCount=0、skillBindingCount=0，active 数均为 0。

全局定义对两租户可见符合目录语义；租户实例与 Binding 均为空，证明本阶段未越界执行安装或激活。

## 4. A0-V 影响

发布前的 `AIP_ECOMMERCE_CATALOG_INVALID` 三个 HTTP 409 已消失。当前 19 个 blocker、1 个 unverified 中，目录缺口被替换为更精确的 installed/runnable/available 与 binding 未就绪事实；总数增加不代表回退，而是 API 可读后暴露出细粒度准入状态。

本阶段未关闭 Workshop/Bundle 安装、租户 Agent 安装、调查 StageTemplate/ResponsibilityPlan、SourceReadiness、Model/Route/Health/Chain/Budget 或跨租户 exact-id 反查。恢复库来源仍是 2026-08-05 历史备份，目录状态必须标注为本次隔离重建结果。
