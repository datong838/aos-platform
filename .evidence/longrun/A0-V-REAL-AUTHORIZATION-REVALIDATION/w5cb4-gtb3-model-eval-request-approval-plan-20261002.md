# GT-b3 一等 Model Eval 申请与原 maker/checker 绑定方案

基线 AOS-001086 / m1 `62b0fcda`，Task `W5CB4-GTB3-MODEL-EVAL-REQUEST-APPROVAL-20261002`。已复习 231-5、BG00GT、GT-a/b0/b1/b2、原 `AipActionStore`/risk/Executor、Model Store 与 EvalPack。用户批准评测用途设计、代码、隔离验证；当前真库只读、真实 Provider/Host 不启。

## 源码结论与边界

- 原 Action Proposal/Decision 已实现 maker/checker、审批事件及撤销，但通用 Action 不认识 Model Eval 申请或用途；只填 `purpose='quality-eval'` 不构成准入。Network policy 的专用 Producer/Guard 展示了当前元数据、租户 DB role、membership、head 和精确 payload 在 Action 写事务中重验的模式。
- 原 Action executor 只阻断 Policy、首生内容与 analysis bootstrap；新 Model Eval ActionType 必须明确禁通用 executor，批准事件只能由后续 GT-b4 intent 消费。
- GT-b1 的 `require_current_model_eval_candidate_for_update` 可在请求创建及 Action 申请/审批事务内锁当前 Model head；GT-b2 已以独立 PG 验证行锁。GT-a 只读预检不得作为批准输入。
- 原预算 Store 要求 Task，容量池要求 active Model/Route 与 AgentRun；本波不伪造这些身份，不发发送意图。费用与物理容量共用锁仍由下一波 GT-b4 解决。

## 本波最小可审计交付

1. 新表 `aip_model_eval_request`：tenant、稳定 request/idempotency key、申请 canonical hash、Model source/next-active target/head、exact EvalContract/Suite/Provider/Price/Quota/Budget refs、费用上界、过期时刻、maker、创建时刻；不可变、唯一键、FORCE RLS、租户 FK 与 `aos_runtime` 最小权限。只准创建/读取，无执行状态，重放必须同 hash。迁移 `a0v_133_model_eval_request.py` 只在独立 test-only 克隆演练，不碰当前真库。
2. `aip_model_eval_authorization.py` 增严格申请合同，绑定 `quality-eval`、CNY 与正费用上界、时区截止；响应没有 `executionAllowed=true`。`aip_model_eval_request_store.py` 以 serializable 租户事务锁 head、重读 exact candidate、核依赖和幂等后写不可变申请；跨租户/版本漂移/过期拒绝。
3. 固定 ActionType `aip_request_model_eval`，风险 R2 且 makerChecker；`aip_model_eval_action.py` 生成唯一 canonical proposal payload，专用 guard 在 ActionStore 的 create/replay/decide 写事务重读申请、candidate、元数据、member 和 Proposal snapshot，独立 checker；未配 guard 必须拒绝。`aip_action_execution.py` 拒绝通用 executor 领取该 Action。批准事件仍是原 `AipActionStore` 所写，不能仅凭状态文本视为 GT-b4 intent 授权。
4. 测试 `test_model_eval_request_pg.py`：RED 覆盖缺表/缺专用 guard；GREEN 覆盖 exact 成功申请与重放、错租户/hash/head、坏时间/费用、maker=checker、元数据漂移、缺角色、撤销/过期、通用 executor 零调用/零写。相邻 Action/Model/预算门回归；PG 只用 test-only 5433 的隔离 schema/克隆，清理自己创建的对象。

## 顺序与退出条件

先读完 ActionStore/Executor 和具体元数据迁移，再补最终 SQL/字段计划；然后 RED→最小实现→专项/相邻回归→方案一致性/风险复审→verification→m1 精确提交→AOS/Prime/D-wave。浏览器无页面改动，暂不适用。GT-b3 即使通过，也只允许正式审批申请，不能调用 Provider、不能生成 Usage/Report/Gate、不能宣称首次 Model Eval 已执行；GT-b4 必须接共享预算容量及有界发送 intent，GT-c/d/e 再接运输与证据。

## 2026-10-02 源码补读后的精确字段与事务计划

- `aip_eval_suite_revision.target_ref` 是 `AssetRevisionRef`：`assetType=registered_model`、字符串 revision；Model Runtime `VersionedAssetRef` 是 `assetType=RegisteredModelRevision`、整数 revision。申请 Store 只做显式四字段映射比较，禁止直接 JSON 相等或放宽 target hash。Eval Contract 的 `suite_ref` 也必须映射到同一个 exact Suite。
- 申请表主键 `(org_id,project_id,request_id)`；租户内唯一 `(org_id,project_id,idempotency_key)`；列存 canonical request JSON/hash、source/target/head、全部六类 exact ref、purpose/CNY/upper bound/expiry/maker/created_at。数据库检查字段与 JSON 一致，FORCE RLS，追加不可变，`aos_runtime` 只有 SELECT/INSERT。没有状态列或执行权限列。
- Store 在单个 tenant SERIALIZABLE 写事务中先锁 Model head，再比较 Model 原 revision 的 provider/price/quota/budget 绑定；接着只读查询 Suite、Contract、Provider、Price、Quota、Budget 当前版本与 lifecycle/effective window，确认 Suite target exact。事务内锁幂等键后插入；同键同 hash 重放返回原申请，不同 hash 拒绝。截止时间必须晚于数据库当前时间；请求创建不是批准。任何依赖不全失败封闭。
- 原 Action 的 `aip_request_model_eval` 风险下限 R2、maker/checker=true、`executionAllowed=false`、`draftOnly=false`。申请 Action 的 Producer 只能引用已持久化申请；ActionStore 创建、幂等回读及 decide 均复核申请、Model head 与 exact Action snapshot。通用 executor 要单独加拒绝门；该文件不在当前 Task Receipt scope，先登记后改。
