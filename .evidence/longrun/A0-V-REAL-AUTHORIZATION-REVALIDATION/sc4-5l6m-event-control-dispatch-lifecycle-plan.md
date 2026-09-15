# SC4-5l6m EventControl 可选分派生命周期方案

日期：2026-09-16  
基线：`ea0536ef`  
owner：`m1`；不 push；230 L0 挂起。

## 决策

新增一个固定、receipt-first、三阶段的 Host 生命周期：`expand` 在完整九项 extension 组上追加 `ecommerce_growth_event_control`；`fence` 只封锁该可选项；`shrink` 只在已 fence 后删除该项。每次都把全组 `cutover_group_revision` 原子推进一版，所有请求绑定同一当前 Case、SchedulePolicy、安装、代次、execution epoch、runtime revision、组和预期组版本。

三阶段都需要独立 `ecommerce_growth_event_dispatch` ActionApprovalEvent，payload 精确绑定完整请求意图。这样安装包声明、运行状态和用户长期授权不能替代系统内 maker-checker 审批；后续真实脚本可以为每个阶段建立新 Proposal/Approval，但不能复用事件策略启用或普通 cutover 的批准。

## 数据与权限

`a0v_054` 只新增不可变 `extension_event_control_dispatch_receipt` 和一个 restricted SQL 函数。表按 org/project 强制 RLS，runtime 仅 SELECT，maintainer 仅 SELECT/INSERT，UPDATE/DELETE 由触发器拒绝。函数仅接受严格 JSON，请求 key 漂移冲突；要求 serializable、非超级用户、精确 tenant session、当前成员、完整九/十项、统一 extension target、ready/enabled/unfenced runtime 与 exact revision。它不检查签名资产和审批内容；这两项由持有 Registry/Artifact/Action Owner 的 Python Service 在同一事务中复验后，才临时切换 maintainer 调用 restricted 函数。

`expand` 新行 `revision=1`，组版本整体 `+1`；`fence` 使控制行 revision `+1`、fence=true、组版本整体 `+1`；`shrink` 要求前一阶段 exact Receipt、控制行已 fence，删除控制行并把九项组版本整体 `+1`。回执保存 before/after snapshot、请求 hash、actor 和 exact authority hash；同 key 只回放，不再变更分派。

## 签名包与审批资格

Service 通过当前 installation lock 和 ReleasePolicy 复验 growth 的签名声明；除原九项注册资格外，必须有唯一 POST/exclusive 的 event-control contribution，且已签名包导出的 `product-event-control.contract.v1.json` 与 Host 固定合同一致。审批复用当前 AIP 的 exact proposal/approval、租户成员、marking、风险和期限验证；新增 action risk 固定 R2、可执行、maker-checker。

## 文件范围

新增：

- `services/aos-api/alembic/versions/a0v_054_event_control_dispatch_lifecycle.py`
- `services/aos-api/aos_api/ecommerce_event_control_dispatch_lifecycle.py`
- `services/aos-api/tests/extension_runtime/test_event_control_dispatch_lifecycle_pg.py`
- 本方案与验证文档。

修改：

- `services/aos-api/aos_api/aip_action_policy.py`：只增加固定 action type 的 R2 分类。
- `services/aos-api/aos_api/ecommerce_product_event_approval.py`：只暴露受控参数化包装供该固定协议使用，原 schedule/control 行为不变。

## preHash

- `services/aos-api/aos_api/aip_action_policy.py`：`4255c692bb0fe597c5d5c81c97d8c6a6fda0ae57d70c09856a0287fd95cb464f`
- `services/aos-api/aos_api/ecommerce_product_event_approval.py`：`417c9ed0bc3ddf64b61e2a7a4d5fb1730cbc67e66a9ba6ac05d61f2c5a93df10`
- 新迁移、Service、测试：`NEW`。

## 退出与停止条件

1. 隔离 PG 完整验证 expand→replay→fence→shrink、每阶段快照和版本。
2. 漂移 key、缺项/未知项、错误安装/代次/epoch/revision、未 fence shrink、过期/错误审批、未签名或未声明控制合同全部拒绝。
3. 两租户同 key 隔离，canary 无写；非 maintainer 不能直写或调用，Receipt 不可变。
4. 原九项 cutover、ProductEvent control、Action 风险测试回归通过。
5. 任一写结果未知时只按 org/project/key 读取 Receipt；同阶段两次失败停止真实写并保留证据。

本步不迁移主库、不修改 E、不安装 1.9。完成后进入第 2/6 步：把 1.9 纳入 current 四包构建与资格 profile。
