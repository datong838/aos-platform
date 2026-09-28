# W5CB4 E17-h｜当前预算审批与影响预览权威只读审计（2026-09-28）

## 上位与静态合同

- 231-9 BG-00 要求正式更新前显示影响预览和审批；产品方案规定费用/正式资产覆盖前批准绑定 exact revision 与 scope。
- `aip_action_models.py` 的 Action Proposal 可引用 `ImpactPreviewRevision`；`aip_action_store.py` 有 Proposal、ApprovalEvent 的精确状态机和影响预览引用校验。但静态搜索未发现预算修订发布的 ActionType/Proposal 接线，也未发现 `BudgetRevisionCreate`/预算发布路由读取这套批准事件。现有 ActionApprovalEvent 主要绑定具体 Action/预算占用，不能直接当预算配置发布批准。
- `BudgetRevisionSetupPanel` 只创建 draft；E17-e 公开 active POST 422。历史 R1 审批单明示不授权当前 A1/R2 运行，E17-g 已限制历史 bootstrap 指向当前库。

## 当前权威库只读对账

用 `scripts/a0v_current_preview_bootstrap.py` 的当前卷连接参数，只在数据库连接开始设置 `conn.read_only=True`，先断言 `current_database()='aos_current_preview_20260927'`；在 `org-org/dev-project` 对如下表执行参数化 `count(*)`，输出：

| 表 | 当前条数 |
| --- | ---: |
| `aip_action_proposal` | 0 |
| `aip_action_approval_event` | 0 |
| `aip_impact_preview_revision` | 0 |
| `aip_budget_head` | 0 |
| `aip_budget_revision` | 0 |

首次探索查询把 `ILIKE '%budget%'` 内嵌 SQL 遇 psycopg 占位符解析错误退出 1；改为参数 `ILIKE %s` 后只读查询退出 0，预算相关 Proposal 0、approved 0、所有 Proposal 0。未执行写事务或任何 Run/Provider/Host 动作。

## 判定与下一文件级入口

当前没有可供预算 active 发布绑定的 Proposal/Approval/ImpactPreview/预算版本；不能用现有 Action 机制的代码存在、历史 R1 单或测试字符串冒充正式批准。正向配置审批的对象/Owner/差异预览及 Receipt 需先按 231-3/231-9 设计并产出，再在同事务核验后发布 active；公开 HTTP 继续 422。

下一波优先转当前三身份/OCI/Host Owner 的独立只读准入审计，明确受保护来源与每个缺项；同时将预算配置审批方案拆成 ActionType/ImpactPreview、maker/checker、预算精确修订引用、撤销/过期负例和最小文件清单。当前库只读，八类 active 候选 0，首链 pending。浏览器 `browser-pilot` 截图仍未验收。
