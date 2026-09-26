# W5caz｜exact Review Receipt 驱动内容 Plan/Run Owner（施工前）

## 上位方案与现场

- 231-5 §1/§4、231-9 §2：exact 方法评审后内容任务自然承接；人工不补技术 Run 引用；真实能力/审批/预算仍另设门。W5cay 已区分 Task 创建 Ref 与当前可变版本。
- `ReviewAdvanceHostService` 原子写当前安装代次的 Review Receipt、Task、v2 Brief，但正式 Receipt 声明 `taskRunCreatedCount=0`；AIP `create_plan`→`approve_plan`→`create_run`→`start_run` 是唯一公共任务状态机。尚无持久 Review Receipt 自然消费者。不能重写原回执或仅靠 UI 多接口手接线。

## 文件级与最小切片

1. 新增 `services/aos-api/aos_api/ecommerce_content_taskrun_owner.py`：只读 tenant-bounded selector 找当前 Review `ACCEPT`、v2 Brief、未启动内容 Plan/Run 的唯一 Receipt；另在可提交事务内二次核当前 Dispatch/Runtime、Review Receipt hash/target、Task 创建哈希、Brief exact 内容与唯一性。已 claim/未知/旧代/禁入不能盲重试，读回既有 Plan/Run 后才作幂等判断。
2. 复用 `AipTaskStore` 与 `TransactionBoundConnectFactory`，用 Review 中已正式批准且未变更的 GrowthPlan/方法内容确定性编译两个内部步骤（真实内容生成、人工内容评审）；该审批只派生同范围内部 Plan/Run，不授予 Provider/发布/外部副作用。若不能证明批准的 exact 内容覆盖编译 Plan，则保持候选 pending，不调用 `approve_plan`。Plan、Task 状态、Run 与启动 Receipt 同事务提交，防止部分交接。
3. 初波仅创建/启动公共内容 Run 到 `running`，不创建 AgentRun/容量、不生成 Artifact、不假设 Step 成功；新 Run 的 exact 引用经独立读回。下一波接 AgentRun/容量与 `content.generate` 自然命令，再下一波接 Step/Run 正式终态；W5cax 反馈门始终不绕过。
4. 先写 RED：同一 Review 重放/并发只一个 Run；错租户、旧 epoch、撤销/换代、Brief/Task/Plan hash 漂移、未知提交边界均零新增 Run。测试文件 `services/aos-api/tests/extension_runtime/test_ecommerce_content_taskrun_owner.py`、`test_ecommerce_content_taskrun_owner_pg.py`。若需要迁移，则唯一新 head 从 `a0v_100` 向前，不改旧迁移；生产迁移须单独权威与验收。

## 验证与退出

- RED→最小代码→专项/累计/PG→浏览器（无可信实例则说明）→方案/代码复审→verification→m1 commit→D-waves/AOS/Prime 记忆→下一波。运行开关默认关闭、同进程 ACTIVE Runtime Host 且 host-only DB 身份；未获真实安装/审批/Provider 权威不开活体。
- 原 12 Run 不重发、不读商城源；230 L0 挂起，dev-org 只作零 canary；未知结果不重复发命令。若严格审批继承难以证明，本波以清晰的 fail-closed 设计/测试界限结束，不伪造 Run。
