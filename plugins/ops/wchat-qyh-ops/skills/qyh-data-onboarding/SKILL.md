---
name: qyh-data-onboarding
description: Fulfill approved 栖月汇 DataNeed handoffs as a Data OS/FDE worker by using the governed `niushop-qyh` MySQL-over-SSH source, profiling remote Niushop schemas and tables, maintaining P01-P12 or new mapping candidates, producing quality-controlled datasets, and handing Ontology hydration candidates upward. Use only with an explicit DataNeed, TenantScope, purpose, and Data OS/FDE capability binding. Never invoke from Workshop or expose raw database access, SQL, credentials, or source rows to Workshop.
---

# 栖月汇数据接入与水合专家

先读 [源与管道地图](references/source-and-pipeline-map.md) 和 [DataNeed 履行流程](references/data-need-fulfillment.md)。

## 定位

本技能是 Data OS/FDE 的上游接入能力，不是 Workshop 数据查询工具。它负责把经营层提出的语义缺口逐层变成受治理的数据产品和本体候选。

## 启动门

同时满足以下条件才可开始：

1. 有不可变 DataNeed ref，包含 purpose、TenantScope、店铺/时间范围和最小语义需求；
2. 当前执行身份具有 Data OS/FDE capability binding；
3. `niushop-qyh` Source 属于同一 org/workspace，来源为 live 而非 demo/fallback；
4. 只读访问、PII policy、retention、预算和停止条件明确；
5. 不存在并发的同源写入或 Schema 变更任务。

任一缺失即 `BLOCKED`，不得用 Workshop 登录态、数据库秘密或临时 SQL 绕过。

## 履行链

1. 解析 DataNeed，只保留回答问题所需的最小语义和字段。
2. 经 Data OS Source `niushop-qyh` 发现远程 Niushop Schema、表、字段、键、状态和最小脱敏样本。
3. 先匹配现有 P01–P12 mapping；缺口才创建 MappingCandidate，不复制已存在管道。
4. 执行 grain、identity、scope、状态、时间、缺失、唯一性、孤儿、分布、PII 和新鲜度 Profile。
5. 生成或更新 Dataset，附 revision、cutoff/watermark、quality、lineage、mapping 与 Evidence。
6. 形成 Object/Link Candidate，交给本体 identity/reconcile；本技能不能自行标记 Confirmed。
7. 返回 DataFulfillmentReceipt，引用 Dataset/Profile/Mapping/Ontology Candidate、质量结论、冲突、未知和 nonClaims。
8. Workshop 只收到 Receipt 和受控投影，不收到源表、SQL、连接参数或任意数据库访问权。

## 禁止事项

- 不直接写远程 MySQL，不执行 DDL，不修改商城业务数据；
- 不把 Schema 存在、采样成功或 Dataset READY 当成本体已确认；
- 不把 demo/fallback、旧行数、旧测试或旧同步时间当当前真实证据；
- 不返回手机号、地址、openid、支付材料、物流号、密码、密钥或完整订单明细；
- 不允许 Workshop 以“诊断方便”为由获得 Source/Preview/SQL 权限；
- 不因同属一个插件而合并 Data OS/FDE 与 Workshop 的运行身份。

## 输出状态

只使用：`BLOCKED`、`PROFILED`、`MAPPING_CANDIDATE`、`DATASET_READY`、`ONTOLOGY_CANDIDATE`、`FULFILLED`、`CONFLICTED`。`FULFILLED` 表示 DataNeed 已返回可审计数据产品，不表示外部平台动作或经营结果成功。
