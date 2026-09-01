# AIP P7 验证记录

- 完成时间：2026-09-02T01:46:03+08:00
- 基线提交：`5e2250f24195a0379c5e49ad6d0d5b691a0858e7`
- 真实租户：`org-org/dev-project`
- 隔离租户：`dev-org/dev-project`
- 外部副作用：0

## 方案一致性

1. 六数字同事均按“业务输入 → 已版本化 Logic → 数字同事产出 → 工作台贡献 → 结果回读”展示；Logic 数量与运行状态只取权威目录回包。
2. 工作台深链携带 `colleague` 与 `focus=contribution`，页面能定位数字同事介绍浮层并返回目录；未创建演示任务。
3. 文档导入区明确业务来源、类型、敏感级别和保留策略；只有服务端返回 Receipt 后才进入已接收态。
4. 自定义提取模板支持中文字段、校验规则、模型路由、成本、审批门、CAS 新版本、版本比较与回滚。
5. 服务端以保存的真实字节解析；自定义模板按 exact template id/revision 执行，不再回退默认财务字段。
6. 文档向任务协作助手和 Logic 画布交付时只传 exact document/lineage 上下文，不自动创建 Task、Run、AgentRun 或 Logic。

## 新鲜验证

- 后端专项：`53 passed`（文档真实字节、模板 exact 执行、版本/CAS/回滚、Receipt/Lineage、跨租户与既有 DocIntel 回归）。
- Web 专项：`8 files / 135 tests passed`。
- TypeScript：GREEN。
- Vite production build：GREEN（367 modules；仅既有 chunk-size warning）。
- `git diff --check`：GREEN。
- 内置浏览器：
  - 六数字同事目录完整展示六条业务闭环；导购顾问“回读工作台贡献”真实点击到日常任务总控并定位介绍浮层。
  - 文档智能在栖月汇当前租户完成新建模板 v1、保存 v2、回滚 v1 生成 v3、比较 v1→v3；页面与完整侧栏可见。
  - API 重启后可信空态不注入示例文档；模板写操作只用于当前开发租户配置验收。

## 证据

- `p7a-shopping-advisor-contribution-final.png`
- `p7b-document-governance-final.png`
- `p7b-template-version-rollback-final.png`

## 边界与后续

- 本波没有 Provider 调用、Secret 解析、真实客户触达、业务发布、迁移、路由切换或 Release。
- P8 必须继续完成 25/25 页面累计浏览器、合同/权威追溯、双租户、三视口、键盘与全量回归；不得把本记录当作发布许可。
