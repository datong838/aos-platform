# 栖月汇 M2 三类守护策略真人审批入口方案 r1

## 1. 背景与当前事实

- 唯一正向租户为 `org-org/dev-project`，开发期跳过登录只用于本地页面预览；费用、预算、配置、审批及运行仍要求真实 OIDC 登录。
- Budget 已有正式候选、审核意图、只读对账入口。
- Egress、Data Classification、Quota 已存在 revision 2 draft，以及底层不可变提案、maker-checker、一次性审核、一次性激活实现，但缺少可部署的产品 API 与页面入口。
- `aip_guard_policy_activation.py`、`aip_guard_policy_issuer.py`、`aip_guard_policy_consumer.py` 是既有权威实现，本任务不得修改或复制其业务规则。
- 本任务只补“提案 + 真人审核意图 + 只读对账”接线。批准后仍不自动消费、不激活、不调用模型或 Provider。

## 2. 产品目标

让机器起草人能对精确 draft 创建 15 分钟内有效的激活提案；让另一位已登录的 owner/admin 真人在页面核对租户、策略类型、ID、revision、目标摘要和风险后，明确批准或拒绝；网络/超时未知时只能查询原请求，不能换幂等键重发。

本增量完成条件：

1. Egress、Data、Quota 共用一个严格类型化入口，不接受网络策略或任意 payload。
2. 浏览器不接收或保存服务凭据；Bearer 只随当前请求进入 API，并只传给隔离 issuer。
3. 创建提案与审核决策必须由不同 subject 完成，且两者均属于当前租户 owner/admin。
4. 决策结果仅产生不可变 approval event，返回 `activationAuthorized=false`；后续消费/激活必须另行显式执行。
5. 未配置隔离 issuer 时 fail-closed 为 503；开发期登录旁路不得把它变成伪批准。

## 3. 最短实现路径

### 3.1 后端

- 新增 `aip_guard_policy_issuer_contracts.py`：只定义 version 1 的 decision/inquiry IPC 合同，复用现有 `GuardDecisionCommand` 校验。
- 新增 `aip_guard_policy_issuer_ipc.py`、`process.py`、`client.py`：沿用网络 issuer 的长度上限、唯一 JSON key、Unix socket peer 身份、单次发送和未知结果语义；进程内部只调用既有 `GuardPolicyIssuer.execute/inquire`。
- 新增 `aip_guard_policy_issuer_application.py`：API 侧再次核对当前 Principal 与 Bearer 是同一 OIDC subject/tenant；在发送前持久占用一次 decision attempt；unknown 只准 inquiry。
- 扩展 `aip_runtime_guard_policies.py`：
  - 创建精确 guard proposal；
  - 提交真人 decision intent；
  - 查询原 decision intent；
  - 不增加 consume/activate API。
- API 启动配置沿用 app state 注入；无配置时明确关闭。

### 3.2 前端

- 新增 `aipGuardPolicyApproval.ts`：严格解析 proposal/decision/readback，拒绝 tenant、hash、revision、policy kind 漂移。
- 新增 `GuardPolicyApprovalPanel.tsx`：显示待审精确摘要，批准/拒绝按钮不预选；提交一次后冻结原请求，只显示“查询原请求”。
- 挂载到 `ModelRuntimePage.tsx`。不修改 Cursor 的登录旁路，不把未登录状态解释成批准。

## 4. 测试顺序

1. RED：IPC 合同拒绝未知字段、错误 schema、Bearer 泄露、跨租户、错误 action type。
2. RED：API 未配置 issuer、maker=checker、非 OIDC、If-Match 漂移、重复幂等键冲突、unknown 后重发均关闭。
3. GREEN：三种 policy candidate 均能创建严格 proposal；独立 checker 的批准/拒绝产生可只读回读的 event，且 `activationAuthorized=false`。
4. RED/GREEN：前端仅在完整精确数据下允许审核；身份变化、响应漂移、unknown 都冻结写按钮并保留查询入口。
5. 相邻回归：现有 Egress/Data draft、Network approval、Budget approval、ModelRuntime 页面测试保持通过。

## 5. 数据与运行边界

- 不迁移或写当前业务数据库；只运行 Fake/离线测试，若需 PG 则另行登记隔离资源。
- 不读取商城源，不启动 Host/worker/Provider，不调用模型，不触发费用。
- 不代替用户签署，不使用合成 approval event 作为真实验收。
- 不重放旧 12 Run、failed/actual/unknown，不 push 或外发。
- 页面、测试、接口 200 只算工程接线；八阶段仍为工程 2/8、真实 0/8，直到本人完成原生审批并另行消费、激活和真实业务链验收。

## 6. 风险与回退

- 最大风险是把 API 进程变成高权限 issuer；因此必须使用独立 Unix socket 进程和专用数据库身份，API 不能直接获得 issuer DB 连接。
- 最大一致性风险是审批后源 draft 漂移；既有 GuardPolicyApprovalGuard 会在同一事务重核 source、proposal hash、binding、membership 和数据库时钟。
- 网络断开可能发生“提交成功但响应丢失”；attempt 先落盘，之后只 inquiry，不自动重发。
- 前端发布问题可只回退新增挂载和页面；既有草稿、提案、审批事件均不可删除或改写。

## 7. 本轮技术债

- Quota 当前配置入口位于 Capacity 工作台，不在本 Task 修改；审批面板先接受精确 proposal ID/readback，不重复实现配额编辑器。
- issuer 运维安装、systemd/launchd 及正式 current stack 部署属于后续独立 Task；本任务只交付可部署源码与离线契约测试。
- 视觉统一、批量列表、通知等非功能需求暂不做，记债后置。
