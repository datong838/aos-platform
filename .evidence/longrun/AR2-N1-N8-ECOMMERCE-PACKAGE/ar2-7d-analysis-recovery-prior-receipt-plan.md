# AR2-7D Analysis 恢复前序 Receipt 权威施工卡

日期：2026-09-09
基线：`m1@65b5d822`
状态：施工中，不推进 AR2-7D GREEN

## Rules 与现状

- m1 独占串行；方案先行、最小更改、专项与邻接自测、证据后提交；不 push，230 L0 挂起。
- 复习 231-6 D1、包内 `analysis_runtime.py`、`aip_business_investigation_data_saga.py`、现有 `AnalysisAdvanceHostService` 和统一 runtime Receipt Store。生产 Host 当前只接受 `runtime.analysis.start`，固定返回不完整 `PREPARING`；因此 readiness seal 仍只能保留前五项。
- 本切片不把类／方法形状当接线证明，不生成 `WAITING_DATA`、`RUNNING`、`UNKNOWN` 或 `RECONCILING` 状态，也不解除 production registry seal。

## 本切片目标

1. 将 Analysis 命令解析拆为严格的 START、RESUME_DATA、RECONCILE_UNKNOWN 三种包络；每种都重算完整 requestHash，拒绝额外字段、弱类型 revision、错误 ref 类型、无时区／超窗 observedAt、重复或超量 Evidence。
2. 为 `BoundEcommerceGrowthRuntimeStore` 增加受限的 exact Receipt 读取：固定租户、operationId 和 `receiptRef`，逐字段重算并核对持久 request/response/target ref；禁止按调用方提供任意 SQL、跨 operation 或仅凭 resourceId 命中。
3. `AnalysisAdvanceHostService.revalidate` 对恢复命令先回读 prior AnalysisRuntimeReceipt，并要求 exact ref、输入 Occurrence/Case/Profile/cutoff、前序 phase/action 与恢复模式一致。RESUME 只接受 WAITING_DATA；RECONCILE 只接受 UNKNOWN/RECONCILING 且保留同一 target Receipt。
4. execute/verify 在后续真实 Data/Checkpoint/target Owner 接通前继续稳定 fail-closed；START 行为与已存在 Receipt 重放保持不变。

## 文件与验证

- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`
- 修改 `services/aos-api/aos_api/ecommerce_growth_runtime_store.py`
- 修改 `services/aos-api/tests/extension_runtime/test_ecommerce_analysis_advance_host.py`
- 修改 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_runtime_store.py`
- 如需数据库行为反证，最小修改 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_runtime_store_pg.py`

先跑新增严格解析与 exact read 单测，再跑 Analysis 包合同、DataFulfill、runtime Store/registry/Router 邻接；随后运行 compile、diff、AR2 closure、memory validate。任何真实 Provider、源读取、外部发布、生产迁移或真实租户写入均为零。
