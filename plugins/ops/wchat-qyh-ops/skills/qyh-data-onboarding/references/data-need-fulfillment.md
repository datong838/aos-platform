# DataNeed 履行流程

## 输入

- DataNeed exact ref 与 revision；
- purpose、org/workspace、店铺、平台、时间窗；
- requiredSemantics 与 minimumFields；
- currentEvidenceRefs、gap、PII policy、retention；
- acceptance、deadline、priority 和预算。

## 分步执行

1. **Preflight**：验证 DataNeed revision、scope、Source ownership、read-only policy 和执行身份。
2. **Coverage**：对照 P01–P12 Dataset/Object/Link，判断是新鲜度问题、质量问题、映射缺口还是源缺口。
3. **Source discovery**：仅 Data OS 内部查看相关 Schema/表/字段；范围随 DataNeed 收缩，不做无目的全库导出。
4. **Profile**：确认 grain、identity、状态轴、事件时间、处理时间、单位、币种、缺失、唯一性、孤儿和 PII。
5. **Mapping**：复用或形成 MappingCandidate；记录过滤、增量、软删除、对账和降级规则。
6. **Dataset**：构建受租户隔离的数据产品，记录 revision、cutoff/watermark、quality、lineage 和 Evidence。
7. **Ontology handoff**：提交对象/关系候选给 identity/reconcile；不越权 Confirm。
8. **Receipt**：返回履行状态、精确 refs、质量、冲突、未知、阻断和 nonClaims。

## DataFulfillmentReceipt 最小字段

- `dataNeedRef`、`status`、`scope`、`purpose`；
- `sourceRef` 与 source mode，不含连接参数；
- `datasetRefs`、`profileRefs`、`mappingRefs`、`ontologyCandidateRefs`；
- `cutoff`、`watermark`、`quality`、`lineageRefs`、`evidenceRefs`；
- `conflicts`、`unknowns`、`piiMarkings`、`nonClaims`；
- `fulfilledAt`、executor capability binding ref。

Workshop 根据 Receipt 回读 Confirmed 投影。若只有 `ONTOLOGY_CANDIDATE` 或 `CONFLICTED`，页面必须保持 blocked/待补证。
