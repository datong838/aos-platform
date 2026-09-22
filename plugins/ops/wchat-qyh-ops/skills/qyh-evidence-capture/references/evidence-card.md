# Evidence Card 模板

```yaml
evidenceId: qyh-<domain>-<date>-<sequence>
evidenceType: OBSERVED_UI | SCHEMA_EVIDENCE | DATA_AGGREGATE | OWNER_EXPLANATION | RECEIPT
businessQuestion: ""
sourceRef: "页面语义/安全数据集/文档引用；不含秘密"
scope: "店铺、对象、时间窗、页面范围"
collectedAt: ""
cutoff: ""
methodRevision: ""
quality: COMPLETE | PARTIAL | STALE | CONFLICTED | UNKNOWN
confidence: HIGH | MEDIUM | LOW
supports:
  - ""
nonClaims:
  - ""
privacyMarking: public | internal | confidential | pii-restricted
conflicts:
  - ""
nextEvidence:
  - ""
```

页面截图、数据聚合和负责人说明必须分卡。结论引用多卡，不把说明伪装成系统事实。
