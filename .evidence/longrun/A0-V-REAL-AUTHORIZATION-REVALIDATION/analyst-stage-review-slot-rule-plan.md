# 经营参谋阶段评审职责槽纯规则方案

日期：2026-09-12

基线：`61de33c4`

状态：实施完成，宿主权威读取与运行装配待办

## Store 审计结论

StageDecision Store 已绑定 HostTransaction 与 TenantScope，并在宿主事务中执行 advisory lock、
Receipt-first、head CAS、相邻 revision、事务时钟、历史回读及跨租户隔离。它是平台 Owner，
不能作为包可直接访问的数据库端口。包只接收宿主已核验后的最小值投影。

## 本波目标与合同

从 `ecommerce_analyst_stage_review_authority.py` 拆出职责槽纯规则：

- stage 仅允许 portrait、diagnosis、solution-design；actor 必须规范非空。
- slotId 必须是 `analyst.{stage}.review`，responsibilityType 必须是 independent_review，
  returnStage 必须等于 stage。
- requiredCapabilityIds 必须是严格空列表；人工独立评审不借用机器 capability。
- assignee 必须是 human_principal、version 严格为 1、resourceId 等于 actor。
- assigneeResolutionReceiptId 必须规范非空，但其存在、有效期、snapshot/content hash、成员身份与
  exact selection 仍由宿主 Owner 在事务锁内复核。
- 不迁移数据库、TenantScope、Principal、ResponsibilityPlan Store 或 Receipt；不修改宿主文件、
  Candidate、OCI、Registry、Installation 或 operation。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_stage_review_authority.py` | `1e549eaca433462b9ea807241dfd98443e5f1b0f46940caf9f89c022638f7186` | 验证输入；宿主权威实现不改 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_stage_review_authority.py` | new | 职责槽纯领域规则 |
| `services/aos-api/tests/extension_runtime/test_analyst_stage_review_slot_rule.py` | new | 正负合同与隔离 import |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `afa5432ad4c7b001fc9d37829016e3481875afa28a735aef3016a9084a94e100` | 登记 9.13 切片 |

## 退出与下一门

三阶段合法槽、所有字段漂移、布尔 version、额外 capability、空 Receipt、宿主既有结构回归、
独立 import、编译和 AR2-7 closure 全绿后提交。下一波评估 stage review command 中可独立迁移
的命令构造/领域比较；当前 Owner 与运行装配仍 PENDING。
