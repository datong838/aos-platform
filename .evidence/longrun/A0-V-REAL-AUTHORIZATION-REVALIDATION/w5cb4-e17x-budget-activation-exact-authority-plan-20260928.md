# W5CB4 E17-x｜正式 BudgetRevision active 精确审批链文件级方案

## 已复习的上位约束与现状

231-3 要求 runtime config 在同一事务以当前 head、原 payload/hash、数据库时间读取有效 active BudgetRevision；231-5 要求批准绑定精确预算上限、对象、有效期与当前执行代次，并由系统自然续跑；231-9 BG-00 要从产品入口完成真实配置/禁入/恢复。E17-w 当前八候选均 0。`routers/aip_budgets.py` 在 Store 前拒 active 422；`aip_budget_store.py:publish` 自身没有审批输入，历史隔离脚本和 PG fixture 直接调用它创建 active，不能把这种测试来源当当前正式批准。

现有 AIP Action proposal/approval 有租户、版本/哈希、maker≠checker、到期、幂等与事件，但 `CreateImpactPreviewRequest` 强制 Task/Plan/Brief/Evidence/Eval/Responsibility/Stage，不适合预算配置本身。不能借用一个无关业务任务的 ImpactPreview 来批准预算，也不能把通用 ActionType 或安装 preview maker/checker 当预算激活批准。当前 auth 开发回退主体亦不能作正式 checker。

## 设计边界和施工顺序

1. 将预算激活请求定义为现有 Draft 的**精确下一修订**：scope、budgetId、expected head version/revision/hash、拟 active 的 `BudgetRevisionCreate` 全量 canonical hash、每日/月度上限、币种、窗口、Owner、超额审批人、有效期。申请者由已验证的 Principal 派生，不接受 body 自报 maker/checker/tenant。
2. 预算专属影响预览必须绑定上述目标哈希及当前 head，并明确日/月新增额度与现有占额/未知账单的保守影响；在未有正式只读费用来源时 readiness=`blocked`，不能填 0。预览冻结后修改预算或 head 使它失效。该模型与生产 Task ImpactPreview 分离，复用通用哈希、租户和不可变 revision 约束。
3. 决策必须由正式权限系统解析 checker，maker≠checker；批准绑定精确预览/目标 hash、额度/有效期并有撤销/过期；非正式开发回退主体无权决策。当前真实用户批准/额度缺失时只实现与隔离验证合同，当前实例继续 422。
4. 激活与批准消费在同一 scope 事务内锁预算 head/审批，按 DB 时间复核精确内容、head、有效窗口、审批未消费/未撤销/未过期、费用上界及幂等 key，再写 append-only BudgetRevision、Receipt 和审批消费；未知结果只读对账。不得先解开 HTTP 422 后补校验。
5. 新持久结构如需 `a0v_110`，必须另波做当前备份一致性/克隆全链/零执行窗口/迁移切换；当前库始终只读，不能因代码头领先强行重启。先不添加迁移或当前真实数据写。

## 本刀文件与 RED 门

- **先行合同/纯校验（本刀）**：新增 `services/aos-api/aos_api/aip_budget_activation_authority.py` 的无数据库纯校验，接受服务端读取的预算目标与精确批准证据；输出只允许 `blocked` 或 `eligible`，其中没有当前有效批准、预览未冻结或目标 hash/租户/head/时间不匹配一律 blocked。不得把调用方传入的对象直接当正式权威，必须由后续 Store 在同一事务读出后调用。
- **RED**：新增 `services/aos-api/tests/aip/test_aip_budget_activation_authority.py`，先覆盖错租户、错对象/版本/哈希、同人、过期/撤销、预览未冻结、金额窗口变化、重复消费；正例只证明纯合同满足，不证明当前正式审批已存在。
- **后继 Store/API/迁移**：`aip_budget_store.py`、`routers/aip_budgets.py`、`aip_budget_contracts.py`、Action/预览 authority 及迁移/PG 测试；先完成正式生产者及事务消费，再替换 active 422。此处只列文件入口，不提前改动。

## 验收与禁令

纯合同 RED→最小实现→专项回归→上下文与 D-waves 登记。必须说明纯合同不赋权、不消费审批、不解决当前 0 候选；API active 422、Host/worker/Provider 0，当前库只读。后继 E17-y 再按正式产品流程实现持久权威，未经批准不启当前实例。无商城源、dev-org 写、旧 Run、手工 Run、230 L0。
