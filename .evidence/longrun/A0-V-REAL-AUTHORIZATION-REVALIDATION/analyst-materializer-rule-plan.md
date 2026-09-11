# 经营计划任务图纯展开规则包化方案

日期：2026-09-12

基线：`e7c3f47a`

状态：实施完成，宿主 Task/图写端口接续待办

## 前置审计结论

GrowthPlan 批准是认证 Principal 发起的宿主 HTTP 命令，不是 extension operation。现有 Store 的
`publish_plan` 已在单一事务内先查幂等 Receipt、锁定 head、校验 expectedVersion、执行 CAS、
写 revision 与 Receipt。禁止新增包发起的第二审批端口；未来包规则接缝只能作为宿主批准流程
内部的确定性计算，不能获得 Principal 或发布权威。

## 本波目标

迁移 `ecommerce_analyst_materializer.py` 中不需要 Store 的纯规则：从已由宿主读取的 approved
exact GrowthPlan 生成 eligible CanonicalTaskRequest，并在宿主 Task Owner 返回完整 exact Task
映射后组装确定性 TaskGraphRevision。创建 Task、判断 current head、发布 TaskGraph、幂等 Receipt
和事务仍留宿主。

## 合同

- plan 与 planRef 的类型、ID、revision、contentHash 必须 exact，且 plan 为 APPROVED。
- 只展开 eligible item，保留顺序、taskType、title、priority，并将 objective/planId 写入目标。
- Task Owner 返回的键集合必须恰好等于 eligible itemId；每个值必须是 exact Task ref。
- graphId、actor 必须规范非空，now 必须带时区；映射一对一，数量守恒，图 hash 与宿主现行算法一致。
- 不访问数据库，不创建 Task/Receipt，不接受租户覆盖，不注册 operation，不修改 1.4.0。

## 文件与 preHash

| 文件 | preHash | 修改 |
|---|---|---|
| `services/aos-api/aos_api/ecommerce_analyst_materializer.py` | `e992f722a94c8f0f048ad1822ea359a95aca50cdef4ccb58429cfe7f5c8924fd` | 验证输入；宿主兼容编排不修改 |
| `bundles/solutions/ecommerce-growth/backend/ecommerce_growth/ecommerce_analyst_materializer.py` | new | Task 请求与 TaskGraph 纯展开规则 |
| `services/aos-api/tests/extension_runtime/test_analyst_materializer_rule.py` | new | 宿主 parity、负向边界、隔离 import |
| `.evidence/longrun/AR2-N1-N8-ECOMMERCE-PACKAGE/closure-manifest.md` | `7736c61f57f380b2adfd3c7a4774a449e22a6531aae1f2ed4d0ed61de88258d5` | 登记 9.11 切片 |

## 退出与下一门

合法 Task 请求和 TaskGraph 与宿主逐字段一致，负向映射/引用/时间合同、独立 import、宿主回归、
编译与 AR2-7 closure 全绿后提交。下一波评估 `stage_decision` 的领域 DTO 拆分，继续避免迁移
TenantScope、数据库和 AIP Owner；29 项整体保持 PENDING。
