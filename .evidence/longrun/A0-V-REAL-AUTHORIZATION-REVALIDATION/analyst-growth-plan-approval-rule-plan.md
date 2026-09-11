# 经营计划审批纯规则包化方案

日期：2026-09-12

基线：`8801589a`

状态：实施完成，宿主事务端口待办

## 判断

产品方案要求经营参谋形成的 GrowthPlan 必须经过 exact 人工评审，批准不等于允许外部动作；
外部动作仍逐项经过 Proposal、Approval、Lease、Attempt、Receipt。当前宿主审批 Service 混合了
领域状态转换、当前头读取、幂等 Receipt 和持久化。本波只迁移可独立验证的 DRAFT → APPROVED
相邻 revision 纯规则，为后续宿主窄写端口准备稳定包内合同。

## 合同与边界

- 输入 draft 必须与 exact draftRef 的类型、ID、revision、contentHash 完全一致。
- path planId、expectedVersion 和已由宿主判定的 current 标记必须匹配；current 必须是严格布尔值。
- actor 必须非空、无首尾空白；approvedAt 必须带时区。
- 只允许当前 DRAFT 生成 revision/version 各加一的 APPROVED successor；priorRef 固定为 draftRef，
  approvedAt/createdAt/createdBy 由审批输入决定，contentHash 按规范 JSON 重算。
- 函数不读取数据库、不创建 Receipt、不判断调用者身份、不发布计划、不允许外部效果。
- 宿主旧 Service 保持兼容且不 import bundle；通过合法结果 parity 约束，后续再把事务适配为窄端口。
- 不修改 Candidate、OCI、Registry、Installation 或公开 operation。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_growth_plan_approval.py` | `9d3013da2cfb7f78bc5075183a986155a5515a3ecb24e02abed35ec42b834728` | 验证输入；宿主兼容文件不修改 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_growth_plan_approval.py` | new | 包内审批 successor 纯规则 |
| `services/aos-api/tests/extension_runtime/test_analyst_growth_plan_approval_rule.py` | new | 正例 parity、负向边界、隔离 import |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `cf37aa48fa0a17e9f45a89471ace190e2dd8c4bc23d3784d35c8550c8d2a0c7d` | 登记 9.10 切片 |

## 退出与下一门

纯规则、宿主合法结果 parity、全负向合同、独立 import、既有宿主审批回归、编译与 AR2-7
closure 全绿后提交。下一波评估把宿主审批事务拆为 receipt-first 的 growth 写端口，或转入另一
个不依赖私有 Owner 的纯规则；29 项整体仍保持 PENDING。
