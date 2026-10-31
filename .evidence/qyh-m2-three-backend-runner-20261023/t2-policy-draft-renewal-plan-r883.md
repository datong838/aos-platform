# T2 四策略草稿 revision 2 续期源码方案 r883

时间：2026-10-31（Asia/Shanghai）

## 当前事实与目标

canonical 隔离库中 `m2-three-t2-budget/egress/data/quota` 的 current head 均为 revision 1、version 1、lifecycle `draft`，原窗口于 `2026-10-28T07:10:41.433192Z` 到期。刷新历史仍为 0，因此不得执行 `a0v_166`；也不得激活过期草稿、复用旧 idempotency key 或直接写历史。

用户最新授权允许补齐价格、模型、运行策略和路由配置至 `2027-03-31T04:00:00Z`，但仍不调用；原生最终批准必须由用户本人完成。本片仅为原 M2 合成夹具生成新 revision 2 的 `draft` 请求与 CAS 描述，不进行数据库连接、Store 发布、批准、激活、Provider/模型调用或业务执行。

## 文件范围

- 新增 `.evidence/qyh-m2-three-backend-runner-20261023/t2_policy_draft_renewal_r883.py`
- 新增 `.evidence/qyh-m2-three-backend-runner-20261023/test_t2_policy_draft_renewal_r883.py`
- 更新权威施工清单本节

不修改产品 Store、contracts、迁移、当前业务库、原 revision 1 或 Cursor dirty 文件。

## 最小合同

1. 输入必须恰好是原四个强类型 revision 1 请求，ID、owner、checker、`fixture-draft-only:m2-three-t2`、lifecycle `draft` 与过期窗口精确匹配；任何 active/未知/错租户语义拒绝。
2. revision 2 只允许改变 `revision/effectiveFrom/effectiveUntil`；预算金额、egress allowlist、数据分类、quota 限制和全部 fail-closed 字段逐字段保持。
3. 新 `effectiveUntil` 固定 `2027-03-31T04:00:00Z`；`effectiveFrom` 由未来 actual intent 固定且必须晚于旧窗口、早于截止时间。
4. 每步描述固定 `expectedVersion=1`，新 idempotency key 为 `m2-three-t2-renewal-20270331-{step}`，request hash 使用原 Store 的 canonical hash。
5. 输出仍为 `draft`，不生成 Approval、active policy、Route/Model调用或执行权限。

## RED/GREEN 与后续实际门

先 RED 证明 helper 缺失；最小实现后运行新专项、原 policy draft 专项和静态编译。只有完整源码/测试一致性通过后，才可另写 actual 方案：新短生命周期连接 Task、四步 durable journal、每步写前重核 current head/version 1、原 Store publish、known return 或只读 reconciliation。任何 unknown 只读对账，不重发。

本片完成不改变工程 2/8、真实业务 0/8；后续仍需本人原生批准、正式职责来源、原安装/配置/启用/切流 Owner 路径产生至少两条刷新回执，再执行 native166 savepoint。
