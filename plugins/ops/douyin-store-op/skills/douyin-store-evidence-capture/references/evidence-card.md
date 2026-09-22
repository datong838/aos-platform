# 抖店经营证据卡

```yaml
evidenceRef: DY-EV-YYYYMMDD-NNN
entity: 店铺实体
channel: 抖店
sourceType: VISIBLE_FACT | PARTIAL_VISIBLE_FACT | PLATFORM_CAPABILITY | INDUSTRY_BENCHMARK | OWNER_CONTEXT | HISTORICAL_DESIGN | INFERENCE | UNKNOWN | PERMISSION_BLOCKED
page: 中文菜单 / 页面标题
path: 稳定路径或定位词
observedAt: ISO-8601
businessWindow: 近7日/近30日/近6个月/累计/未知
scope: 商品/订单/达人/搜索/直播/客户等
metric: 指标或事实
value: 值
denominator: 分母或未知
loadState: COMPLETE | PARTIAL | BLOCKED
confidence: HIGH | MEDIUM | LOW
supports: 支持的判断
competingExplanation: 竞争解释
conflictWith: 冲突 EvidenceRef 或无
nextEvidence: 下一补证
nonClaims: 不可据此声称什么
```

同一事实的截图、页面文本和数据产品可建立多个 EvidenceRef，但不得复制成多个独立事实增加置信度。客户隐私字段必须脱敏或不记录。
