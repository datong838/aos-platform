# SC4-5l6k 当前 ProductEvent 正式配置缺口补充方案

日期：2026-09-15  
基线：`f00cfe9f`  
owner：`m1`；不 push；230 L0 挂起。

## 已验证事实

E installation `1c08edfb-ec0d-4abb-a411-7b6ec0d6066a@5`、generation `ebaa620a-8831-4c2a-b971-788383f352f8` 已 ready/enabled/unfenced。真实 P02 Run `scr-a5a23c835eb04a73` 只读取得 65 个商品对象并成功写入 Dataset，57 active、8 deleted；command/derived/dataset 为 1/1/1，recovery claim 为 0，canary 为 0。

ProductEvent Worker 没有产生 Occurrence、Case 或 Run。主库读回证明当前租户不存在 `ecommerce_investigation_schedule_policy_head` 和 `automation_schedule_binding`；这不是源读取失败，而是安装后的真实业务配置尚未建立。

当前 canonical shop refs、`initial_store_analysis` profile/scope、该 profile 的职责与阶段模板已经存在。Case selection 的公开预览因十二类 SourceReadiness 未完成而显示 `SOURCE_READINESS_NOT_READY`；领域包的 `ecommerce_growth_case_put` 正式 Host 入口仍允许建立 DRAFT Case，后续分析必须用原 `WAITING_DATA`、DataRequirement 与恢复链表达数据不足，禁止伪造 readiness。

当前租户只有 `a0v-ecommerce-growth-1.4-runtime-owner=admin` 与 `user:dev=owner`。运行时 owner 必须执行且不能批准自己的执行；当前审批门的 checker 角色只接受 `admin/approver/aip_approver`，而 workspace 正式成员模型只提供 owner/admin/editor/viewer，故两名现有成员不能组成 maker/checker/executor 三方链。应由现有 tenant owner 经正式 workspace member 入口增加一个用途受限的 checker 身份，角色为 admin；不得改原两名成员角色。全局 `meta_action_type` 尚缺 `ecommerce_growth_schedule_put` 与 `ecommerce_growth_event_control`，而现有包 manifest 只有 actionTypes 权限声明，没有动作类型定义随安装落地。这些都是“可安装、可重装后无需开发者接线”的真实生命周期缺口，必须进入后续包配置计划。

## 本次主路径

1. 扩展现有私有状态执行器；每个 action 先冻结 0600 intent，再通过正式 Store、AIP Action 与当前 canonical router 执行；存在 result 时只读，不以新 key 重发未知结果。
2. `configure-brief` 创建并冻结“栖月汇全店基线与商品尖刀验证”真实 TaskBrief，来源引用本次 P02 Dataset/Run，目标是识别商品结构、在售/下架变化和后续数据缺口，不预填经营结论。
3. `configure-case` 使用当前 shop/profile/scope exact refs，经 `ecommerce_growth_case_put` 建立唯一 `initial_store_analysis` DRAFT Case，再走既有 Case lifecycle 正式 transition 到 ACTIVE。脚本不得直接插 Case 表。
4. `configure-reviewer` 由 `user:dev` 经正式 workspace member 入口幂等建立 `a0v-ecommerce-growth-1.4-approval-checker=admin`；若同名成员已存在则必须精确匹配。该身份只用于本链内部 R2 审批，不能成为 maker 或 executor。
5. `configure-action-types` 仅在动作类型不存在时通过平台正式 ActionType 写入口创建两个精确、空 marking、空 submission criteria 的内部 Case 动作类型；若已存在则要求逐字段完全一致。该动作只补当前租户运行所需平台元数据，不宣称已解决包重装配置。
6. `approve-schedule` 由 `user:dev` 创建 R2 schedule proposal，payload 精确绑定 caseId、schedulePolicyId、policyHash、expectedPolicyRevision、expectedCaseVersion；由专用 checker 独立批准，审批窗口限制在一小时内。
7. `put-policy` 从当前 E SourceSelection、current Case、签名包中的 `ProductEventSchedulePolicy` 与 `prepare_event_case_binding` 生成 revision 1 policy/successor，经当前 scoped canonical router 保存；不得直接写 policy 或 Case revision。
8. `approve-control` 对完整 enable command（移除 approvalRef 后）形成独立 R2 proposal并批准；`enable-event` 经 `ecommerce_growth_event_control` 建立 current binding。
9. `observe-event` 只轮询正式表与 Worker 状态，等待自然创建 ProductEvent occurrence、analysis entry/Run；禁止脚本调用 Worker 内部方法或写 occurrence/run。

## 身份、租户与副作用边界

- 正租户固定 `org-org/dev-project`；`dev-org/dev-project` 只做相关表零写检查。
- TaskBrief 可由当前 tenant owner `user:dev` 冻结；Case、schedule policy 与 event control 必须以 SourceSelection 当前 actor `a0v-ecommerce-growth-1.4-runtime-owner` 执行。
- R2 三方分离：`user:dev` 只制单，专用 checker 只审批，runtime owner 只执行。审批必须绑定当前 ActionType snapshot、payload、policy hash 与 expiration。
- 仅允许内部任务、审批、Case、策略、绑定和分析链状态写；无商城写、发布、触达、投流、改价、库存、订单或履约副作用。
- 首次有效事件后的 occurrence、Run、DataRequirement 与恢复必须由独立 Runtime Host 的 Worker 自然产生。

## 代码范围与 preHash

- `scripts/a0v_qyh_current_product_event_first_chain.py`：`b7d2d6612841ec3fc376ce476cfe2a6f5636bb1055bab10748029796c12b3de7`
- `services/aos-api/tests/extension_runtime/test_a0v_qyh_current_product_event_first_chain.py`：`56a504025b7de9b499c8aad99e85c6361a9c05eb6fb4126cbda99d817a61238b`
- 本补充方案：`NEW`。

不修改 Action policy、Case Store、ProductEvent Store、Worker、Receipt、migration 或已签名包资产。若现有 Host 路由无法完成上述正式配置，先落失败证据并另开最小实现方案。

## 测试与退出条件

1. 静态测试覆盖 action 顺序、固定身份、不可变 intent/result、当前 E refs、真实 TaskBrief 来源、R2 maker/checker 分离、policy/control payload exact 绑定、canary 零写和无 Worker 直调。
2. 相关 ProductEvent approval、Host、control、router 与执行器测试通过；AR2 五类静态扫描保持为零。
3. 真实 TaskBrief 为 frozen；Case 为 ACTIVE 且 schedulePolicyRef 指向保存后的 current policy；两个 proposal/approval 当前有效且 checker 独立。
4. current event binding enabled，引用 E installation/generation/epoch、P02 SourceSelection、Case 与 policy exact refs。
5. Worker 自然创建一次预期 occurrence 和分析入口；幂等复读不增加对象；canary 相关表为零。
6. 落证据并提交。若 event discovery 因 P02 `meta_schedule.enabled=false` 不触发，则下一波只补“已完成历史 Run 可消费、无需保持源 Schedule 开启”的产品语义方案；不得为了触发长期打开真实源调度。

## 后续必须纳入清册的生命周期缺口

当前 reviewer 与 ActionType 初始化完成后，下一轮设计包拥有的声明式配置贡献与 install/configure/uninstall/reinstall 语义：安装时幂等确保 exact reviewer/action type，冲突时拒绝；卸载只撤销包拥有且无其他引用的贡献；重装可恢复；禁入时 event binding 自动 fenced。该项未完成前，不能宣称电商包“安装后无需开发者手工接线”。
