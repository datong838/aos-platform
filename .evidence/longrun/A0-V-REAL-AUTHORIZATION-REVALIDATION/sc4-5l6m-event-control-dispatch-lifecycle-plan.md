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

- `services/aos-api/aos_api/aip_action_policy.py`：`cbcdfd5de12def0fade338050edcd723f9caa6cb0cdf544afb0ca8fafa1328a6`
- `services/aos-api/aos_api/ecommerce_product_event_approval.py`：`35456244303a02b91a1b6a68242dff0279d6f9e0b8dee3a50c1c6bf4dea06fd5`
- 新迁移、Service、测试：`NEW`。

## 退出与停止条件

1. 隔离 PG 完整验证 expand→replay→fence→shrink、每阶段快照和版本。
2. 漂移 key、缺项/未知项、错误安装/代次/epoch/revision、未 fence shrink、过期/错误审批、未签名或未声明控制合同全部拒绝。
3. 两租户同 key 隔离，canary 无写；非 maintainer 不能直写或调用，Receipt 不可变。
4. 原九项 cutover、ProductEvent control、Action 风险测试回归通过。
5. 任一写结果未知时只按 org/project/key 读取 Receipt；同阶段两次失败停止真实写并保留证据。

本步不迁移主库、不修改 E、不安装 1.9。完成后进入第 2/6 步：把 1.9 纳入 current 四包构建与资格 profile。

## 第 3/6 步部署前修订（2026-09-16）

Rules：m1 串行，先方案再修改，真实数据库合同优先，主库部署保持关闭直到生命周期缺口完成。

优先修复测试权威：`test_event_control_dispatch_lifecycle_pg.py` 从 228asset0 原迁移 AST 读取唯一 canonical 函数定义，在隔离 schema 中安装原实现并固定函数 search_path；禁止以 JSONB 文本输出模拟 canonical。对 expand、fence、shrink 和 replay 的 requestHash/contentHash 均使用 Python canonical_sha256 交叉验证；包含中文和嵌套字段。此子步只改测试，不修改生产哈希规则。

后续必须补 exact fence Receipt 和 drain 证据，并以 resumed 安装的 ar2_017 disable/detach 作为 E→F 退役入口；ar2_016 仅用于 validation 窗口。可选分派组版本变化与正式退役的兼容性须有集成实证。前述 46 项通过不关闭这些出口。

## Exact fence 子项（2026-09-16，基线 1043c2de）

收缩的前序权威由服务端从不可变历史中唯一解析，不接受调用者自行声明 fence=true：同租户、安装、代次、epoch、runtime revision、group、targetGroupRevision=当前 expectedGroupRevision，且 installationRef、case、schedulePolicy 与当前请求一致，afterSnapshot 必须等于当前完整组快照。重算前序正文 canonical hash；记录解析到的 receiptId/contentHash 到收缩回执。无回执、任务漂移、快照漂移一律回滚，不删控制入口。审批仍独立绑定原收缩意图。

文件仅 a0v_054（未部署候选）、原 PG 测试与证据。先运行缺失回执/任务漂移/快照漂移红测，再补最小 SQL。运行原正常流、幂等、哈希和隔离回归。此项完成不代表 drain 或 Service 集成完成，主库保持不变。
