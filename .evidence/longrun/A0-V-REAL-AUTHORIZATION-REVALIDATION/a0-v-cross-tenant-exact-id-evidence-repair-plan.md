# A0-V 跨租户 exact-id 证据修复方案

## 1. 缺陷

静态 AIP 目录发布后，当前采集器因任一正向集合非空而移除 `crossTenantResourceIsolation` unverified。AIP Agent/Skill/Capability 定义是全局共享目录，不是 `org-org/dev-project` 独占资源；它们在 canary 可见不能证明也不违反租户实例隔离。

因此“集合非空”不能替代同一租户资源 exact ID 的正向读取与 canary 拒绝证据。

## 2. 最小改动

- 修改 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/a0-v-readiness-collector.py`；
- 修改 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/verify_a0_v.py`；
- 扩充 `.evidence/longrun/A0-V-REAL-AUTHORIZATION-REVALIDATION/test_a0_v_readiness_collector.py`；
- 重采结果并新增验证记录。

不修改 API、数据库、目录或租户数据。

## 3. 判定规则

1. 固定 GET `/v1/aip/agents`，读取正向与 canary 的 tenant-owned AgentInstance 列表；全局定义数量不参与隔离证明。
2. 正向列表为空时，保留 `crossTenantResourceIsolation=NO_POSITIVE_RESOURCE_AVAILABLE_FOR_CANARY_COMPARISON`。
3. 正向存在实例时，选择稳定排序后的首个 `instanceId`，正向 exact GET `/v1/aip/agents/{instanceId}` 必须 200，同一 ID 的 canary GET 必须 404。
4. 任一 exact-id 结果不符合预期即产生 blocker；只有 200/404 同时成立才记录 verified isolation probe。
5. 路径段必须 URL encode；所有请求保持 loopback、GET-only、正文脱敏。

## 4. 验证

纯 fixture 覆盖全局目录非空但租户实例为空仍 unverified、正向实例 exact probe 200/canary 404 才通过，以及 canary 错误返回 200 时失败关闭。当前恢复环境在租户安装前应恢复为 1 个 unverified。

退出标记：`A0V_CROSS_TENANT_EXACT_ID_EVIDENCE_GREEN`，只表示隔离证据判定可靠，不表示已有可用于反查的租户资源。
