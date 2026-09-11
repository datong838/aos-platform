# 经营参谋阶段评审命令身份纯规则方案

日期：2026-09-12

基线：`25127063`

状态：实施完成，宿主编排与发布装配待办

## 宿主编排审计

`ecommerce_analyst_stage_review_command.py` 当前负责私有 query、AgentRun、Artifact、Eval Suite、
Eval Gate、Eval Report、责任计划、人工权限、安装运行时、事务锁、幂等 Receipt 和 StageDecision
Store 发布。这些均依赖平台 Owner 或当前安装身份，必须留在宿主。

模块没有根据业务数据自动替人构造 accept/return/reject/revoke 的规则，因此本波不发明自动评审。
可迁移的纯切片只有确定性 decisionId 计算和提交命令身份校验。

## 本波目标与合同

- decisionId 只由 tenant、taskRun、plan、stage、stageAttempt、subject、Artifact 和 EvalReport
  的现有 exact 值计算，保持宿主 `stage_decision_id` 算法一致；ResponsibilityPlan 仍是决定正文
  的 exact 字段，但依照现行宿主合同不参与稳定目标 ID。
- item 必须是包内 AnalystStageDecisionRevision，经重新解析后 tenant 等于宿主提供的期望租户，
  createdBy 等于规范 actor，decisionId 等于确定性身份，contentHash 等于规范正文 hash。
- 幂等 key 必须是规范非空且不超过 200 字符；expectedVersion 必须是严格非负整数，布尔值拒绝。
- 函数只返回值对象，不证明 actor 已认证、不证明 item/current/prior/Eval/责任计划有效，也不写
  Receipt 或数据库；这些仍由宿主在同一事务中复核。
- 不修改宿主生产文件、Candidate、OCI、Registry、Installation 或 operation。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_command.py` | `2c42badebac8822fb161cb40d86dcc0d9b0228570c9c606152db947789dc8372` | 验证输入；宿主编排不改 |
| `services/aos-api/aos_api/ecommerce_analyst_stage_decision_store.py` | `eba8988bc7c7d2618ad4ff4891b2f91533bc78c2db585dbcd6765e7b4f6e07df` | 验证 decisionId 算法；宿主 Store 不改 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_command.py` | new | 命令身份纯规则 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_command_identity.py` | new | 算法 parity、正负边界与隔离 import |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `cd08376aad1198183f95801fbe0da2b85e78826a1c3d4d6d9c0671dc52e7c949` | 登记 9.14 切片 |

## 退出与下一门

三阶段身份 parity、tenant/actor/key/version/id/hash 漂移、布尔版本、独立 import、相邻包与宿主
合同、编译和 AR2-7 closure 全绿后提交。下一波审计 stage review runtime 的 current 运行链，
继续拆无数据库的 exact 比较；第 9 节整体仍 PENDING。
