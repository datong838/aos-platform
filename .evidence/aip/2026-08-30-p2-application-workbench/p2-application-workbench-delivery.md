# AIP-P2 应用工作面交付证据

- 日期：2026-08-30
- 分支：`m1`
- 基线：`8f709fdc`
- 任务：`AIP-P2-015`～`AIP-P2-031`
- 正向租户：`org-org/dev-project`
- 裁决：`AIP_P2_APPLICATION_WORKBENCH_GREEN / ENTER_AIP_P3`

## 助手工作面

- 任务选择器直接读取当前租户真实 Task，并以中文标题、负责人、状态、更新时间和来源呈现。
- Task、PlanRevision、TaskRun 与 AgentRun 使用 exact ref 恢复；对话线程、参与者、游标、消息、引用和附件元数据由服务端保存，刷新后可恢复。
- 合法运行可暂停、恢复、取消，页面回读最新版本、最终状态和 Receipt；同页聚合计划、产物、证据、审批、时间线、谱系和成本。
- 浏览器证据：`assist-real-task.png`；完整菜单审计补充证据：`../2026-08-30-full-menu-product-gap-audit/01-assist-selected-real-task.png`。

## 六数字同事 Studio

- 六个数字同事均具有中文职责说明、非空 Logic/Skill/Tool/工作台贡献，并支持版本化 Prompt、工具、护栏、预算和模型配置的保存、取消与精确重读。
- 内置浏览器在“数据参谋”实例执行同一权威 TaskRun：`run-a5c2bbfa273143d681bf`，关联 Task `task-45269ad87c4d432a9617`、PlanRevision 1、content hash `db079a7ee52f1e556aba0f60ca100bff89a4e5a477cf97ea4c177553e658ff88`；依次验证开始、暂停、恢复、取消，版本由 1 推进至 5，证据事件由 1 增至 4。
- 同页创建 exact AgentRun `agent-run-61ff5a98187f4b2bb406cd9cecf079a4`，创建后立即以 CAS 取消；取消 Receipt 为 `aip6r-eb4aa97032da400dbebc6767c9322701`，最终状态明确为“已取消（未启动 Provider）”。
- TaskRun 结果只定义为确定性沙箱结果；本轮没有把它冒充模型效果评测，也没有解析 SecretRef、调用 Provider 或产生外部副作用。
- 浏览器证据：`studio-publish-lifecycle.png`。

## AIP 分析师

- 受控查询使用中文经营问题、对象、指标、维度、筛选和截止时间；历史对象类型元数据为空时，只回落到已经冻结的电商属性白名单，不扩张 CustomerLite PII。
- 商品、订单等结果以名称、订单号等业务字段为主体；技术 ID、来源 hash 和内部置信信息留在审计折叠区。
- 表格、图表、地图和原始结果消费同一 QueryResult revision；页面输出摘要、对比、异常、关键假设和不确定性，并聚合来源、新鲜度、权限、证据与谱系。
- 保存探索、复用查询、导出审计说明与移交助手使用同一服务端事实，不用客户端假成功。
- 浏览器证据：`../2026-08-30-full-menu-product-gap-audit/03-analyst-after-real-query.png`。

## 验证

- Web：`268/268` 测试文件、`2355/2355` 用例通过。
- API P2 专项：`39 passed, 4 skipped`；跳过项为环境限定用例，不是失败。
- TypeScript：通过。
- 生产构建：通过。
- `git diff --check`：通过。
- 内置浏览器：助手真实任务选择、Studio 配置/发布生命周期、TaskRun 控制、AgentRun 创建后安全取消、分析师真实只读查询均已逐项操作和回读。

## 安全边界

本轮没有执行 Provider、真实发送/发布、客户触达、改价、迁移、Release 或真实业务数据修改。开发期写入仅限 AOS 自身的 TaskRun/AgentRun/协作线程/配置版本与 Receipt，并保持租户隔离、exact ref、CAS 和幂等约束。
