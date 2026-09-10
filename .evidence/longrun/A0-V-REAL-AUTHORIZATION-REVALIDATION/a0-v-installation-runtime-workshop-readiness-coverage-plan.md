# A0-V 安装运行态与 Workshop 就绪覆盖方案

## 1. 缺口

当前 A0-V 采集器只要求 `/v1/bundle-installations` 集合非空。历史 draft、已回滚或已卸载记录都可能满足该条件，却不能证明电商包当前已激活、运行绑定可派发，也不能证明八个 Workshop 模块已经从同一有效安装投影为可用。该口径存在把半安装或历史记录误判为首链前置就绪的风险。

## 2. 权威依据

- 231-6 将完整纵向验收单位定义为“安装并配置电商包 → 自然槽位 → Case/Run …”，并要求物理生命周期覆盖安装、验证、配置、启用、禁入、卸载和重装。
- `InstallationListItem` 合同规定 `state=active` 时 `activeRevision` 必须等于 `currentRevision`，`etagVersion` 必须等于 `currentRevision`。
- `RuntimeViewReader._derive_control_state` 仅在当前修订绑定 `enabled=true`、`observedState=ready` 且 `operationFence=false` 时返回 `effectiveState=ready`。
- `EcommerceWorkshopModuleProjection` 规定模块 `readiness=available` 时 blockers 必须为空；Workshop 目录由当前有效安装锁投影，不是独立安装权威。

## 3. 最小改动

- 修改 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-collector.py`；
- 扩充 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/test_a0_v_readiness_collector.py`；
- 修改 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/verify_a0_v.py`；
- 重采 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-result.json` 并新增验证记录。

不修改 API、数据库、包安装状态、运行开关或租户业务数据；全部新采集仍为 loopback GET-only。

## 4. 判定规则

1. `/v1/bundle-installations` 必须是结构一致的分页响应，并且恰有一个 `state=active` 的安装；多个 active 安装失败关闭，历史非 active 记录不计入当前就绪。
2. active 安装必须具有非空 `installationId`，且 `activeRevision=currentRevision=etagVersion`。
3. 选中 active 安装后，以 URL encode 后的 exact ID 分别读取正向和 canary 的 `/v1/bundle-runtime-installations/{installationId}`；正向必须 200，canary 必须 404。
4. 正向运行投影必须与 exact 安装 ID 和修订一致，`installationState=active`、`effectiveState=ready`、`currentOperation=null`、`reasons=[]`，并且 binding 非空、同修订、`desiredState=enabled`、`observedState=ready`、`enabled=true`、`operationFence=false`；generation、profileRef、executionEpoch、revision 必须为有效非空值或正整数。
5. `/v1/ecommerce-workshop/modules` 必须结构一致并精确包含八个唯一模块 ID：`ecommerce.task-cockpit`、`ecommerce.content-campaign`、`ecommerce.creator-growth`、`ecommerce.media-studio`、`ecommerce.analyst`、`ecommerce.price-governance`、`ecommerce.customer`、`ecommerce.operations`。每项必须 `readiness=available` 且 blockers 为空。
6. 未找到 active 安装时，不发起伪 exact runtime 请求；以 `ACTIVE_INSTALLATION_MISSING` 记录根因。找到 active 安装后，运行 exact-id 隔离或语义任一不满足均单独产生 blocker。
7. 该覆盖只证明包、运行绑定和八模块的当前准入事实；不替代 SourceReadiness、Agent/Capability、模型链、预算或静态调查 authority 门。

## 5. 验证与退出

纯 fixture 覆盖空列表、只有历史记录、多个 active、修订指针不一致、完整 active 安装、运行态 ready/fenced/disabled/修订漂移、八模块完整可用/缺失/重复/降级，以及 runtime exact-id 200/404 隔离。随后对隔离恢复环境重采，预期把宽泛的集合非空 blocker 改为可行动的 active 安装与 Workshop 缺口，不人工提升 A0-V 状态。

退出标记：`A0V_INSTALLATION_RUNTIME_WORKSHOP_READINESS_COVERAGE_GREEN`。该标记只表示判定覆盖可靠，不表示包已经安装或 A0-V 已 GREEN。
