# SC4-5e6 物流隐私最小化快照

2026-09-14，基线9e65f8ab，Lease A0-V-SC4-SHIPMENT-SNAPSHOT-CANDIDATE，m1不push。

原产品P07要求物流号敏感遮罩。本候选使用完全遮罩：[REDACTED]、trackingNoRedacted=true、trackingNoSourceRead=false；delivery_no原值不被选择，不声称可追踪或源号非空。member_name/trace自由文本一并排除。原读取器的隐私阻断规则无修改。

shippedAt直接绑定delivery_time；与观察时刻独立，零值规范拒绝；ACTIVE仅表示店铺范围内记录存在，不是签收状态。Order.fulfilledBy与父订单完整性尚未物化。

1.9.0源树b52f6a76334528d7c8cde06e802252e6934dd4ead29c35219f976d3f55413e01不变；仅新版本bundle/p07/evals相对修改。37 passed/7既有警告/6.06s；七类合成规范对象评估通过；AR2 1909/187/93五数组空；diff-check与memory validate通过。未采集真实物流行、未发布安装、未完成正式Fulfillment。

SC4-5e6：物流完全遮罩快照1.10.0完成，37项回归通过，七类静态评估通过。物流号不读取并标为完全遮罩，姓名/轨迹排除，零发货时间拒绝而不伪造。树d17d81fefde3e8159c1c18b8a361f6bdac128350c1623b9181540d06d57558cb；静态7/12，主库仍先前2/12。下一CustomerLite最小公开快照与后4类显式源政策，再关联/补齐/主首链。
