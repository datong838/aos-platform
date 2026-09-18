# AM 控制窗口到期失败的正式退休与 direct successor 预案

## 1. 适用条件与当前禁入

- 当前 AM attempt `7d6cc3aa-881d-4aff-ac30-58978d06e85d` 仍为 `running`，本预案不授权暂停、续签、重启、重发、禁用或注册后继。
- AM 当前十二个控制统一有效至 `2026-09-18T18:38:10.986989Z`；attempt Lease 的 heartbeat 只证明 owner 存活，不能延长该业务控制窗口。
- 只有权威 attempt 进入 `failed`，并固定 terminal event、错误原点和 Store 未知提交边界后，才进入本预案的实现与执行阶段。
- 若 AM `succeeded`，本预案立即失效，按既有 `a0v_am_saved_snapshot_recovery.py enable → inspect → disable` 收口。

### 2026-09-19 状态修订

- 首笔 AM attempt 已 failed，但 definition 仍 enabled，Worker 已自然创建第二笔同 request hash attempt
  `38e5c7b9-fa37-4d3f-8f3f-769b995b4db3`。只要该 attempt 为 running，本预案全部写阶段继续禁入。
- 首笔终态没有持久化可审计的安全 reason code；这构成可观测性缺口。退休门禁仍必须以唯一 running=0、
  terminal events、原 Store key Receipt、关系/投影边界及资源状态共同判定，不得用猜测的错误类型替代证据。

## 2. 失败边界判定

1. 锁定 exact attempt、installation、generation、execution epoch、definition rev53、recovery rev17 和十二个原 Run。
2. 核对 attempt/event 终态只有一个 failed，没有并行 running attempt、未知 owner 或重复受理。
3. 核对十二 Run、dataset Receipt、relationship journal、link command 与 conditional retirement 的终态。
4. 用原 link idempotency key 查询 Store Receipt：
   - Receipt 已存在：只读恢复既有结果并验证 `ecom_link`、outbox 与 projection，不得重发；
   - Receipt 不存在：证明 link Store 提交边界尚未跨越后，才允许正式退休；
   - 查询失败、连接中断或结果矛盾：保持 unknown，停止任何会产生副作用的动作。
5. dev-org canary 必须为 0，AM 三个资源与 runtime binding 状态必须与正式 drain/disable 前置条件一致。

## 3. 方案文件级清单（仅 failed 后实施）

### `scripts/a0v_am_failed_retirement.py`

- 以 AL 正式失败退休脚本为结构参考，但所有常量、revision、Receipt 和路由版本均从 AM 当前权威重新固定，不复制历史值。
- 提供 `inspect → pause_failed → drain/disable → retire` 的可重入阶段；每阶段先读取 exact 前置事实，再调用正式 service，不直接更新业务表。
- 每个写阶段使用新 idempotency key，结果写入权限 0600 的不可变证据；未知结果只能按原 key 查询，不得再次提交。

### `scripts/a0v_an_replacement_recovery.py`

- 仅在 AM 完整 detach/retire Receipt 存在后创建 direct successor AN；安装、generation、签名包与资源全部新建，禁止复用 AM live identity。
- 先安装/配置/验证/启用，再进入 successor registration；每个阶段沿用单写者、CAS、Receipt 与租户隔离。

### `scripts/a0v_an_successor_business.py`、`scripts/a0v_an_successor_cutover.py`

- 只接受 AM exact detach Receipt 作为 predecessor；注册外部副作用保持 false，直到正式 cutover 全部完成。
- dev-org 只作为负向 canary，绝不创建 binding、route、resource 或业务对象。

### `scripts/a0v_an_saved_snapshot_recovery.py`

- 从 recovery rev17 和冻结 manifest 继续，不重读 12 个真实来源；创建新的定义 revision、recovery Receipt 与统一执行窗口。
- 原 dataset Receipt、relationship/link command 和 Store idempotency key 继续作为幂等事实；不得把新的 attempt 当作重发授权。

### `services/aos-api/tests/extension_runtime/test_a0v_am_failed_retirement.py`

- 覆盖 failed exact gate、running 禁入、Store Receipt 已存在/不存在/unknown 三分支、资源 drain、路由 detach、重复调用与 dev-org 零副作用。

### `services/aos-api/tests/extension_runtime/test_a0v_an_*.py`

- 覆盖 direct predecessor、安装生命周期、saved snapshot transfer、六小时新控制窗口、successor registration/cutover 和卸载重装恢复。

## 4. 执行顺序与退出条件

1. attempt failed 后先补现场证据和最终常量，再写测试 Red；不得预创建 AN 或写生产状态。
2. 完成 AM pause/drain/disable/retire，每一步都以正式 Receipt 和资源/路由终态作为下一步前置条件。
3. AN 走全新 direct successor 生命周期；冻结数据继续使用，sourceReads 必须为 0。
4. AN attempt succeeded 后执行 inspect/disable，验证 link Store Receipt、1168 条关系或其正式条件退休结果、projection pending=0、资源释放及 canary=0。
5. 浏览器出现 org-org/dev-project 可见电商工作台前，门禁始终 NOT GREEN；测试或脚本成功不等于真实经营闭环完成。

## 5. 回退与停止规则

- 任一步出现 unknown Receipt、CAS 漂移、第二 owner、租户串扰、资源状态矛盾或新控制窗口不足，停止后续写动作并只读对账。
- 已成功提交的正式 Receipt 不回滚、不删除；恢复只走查询原 key、正式 retry/retire/direct successor 服务。
- 本预案不触碰 230 L0，不 push，不扩大现有授权范围。
