# AR2-7D D1 观察与水合精确回读

2026-09-08；同一父任务 AR2-HOST-WIRING-CUTOVER-PLUGGABILITY-BROWSER-ACCEPTANCE，第3/8步。

- 两个公共 Store 新增 read_receipt_exact，仅原不可变 authority 数据 SELECT。
- 校验租户、对应类型、revision=1、receiptId、owner hash、全部业务拆列及 DTO；不依赖 current head、不写、不运行采集或水合。
- 不宣称重算 owner 尚未定义的正文哈希，也不把 succeeded 观察单独当作 fulfilled。
- Red：新增隔离库回读测试两项因方法不存在失败。
- Green：两个专项文件共29 passed /20.94s；包括隔离数据库租户可见性、原计划推进后历史回读、错标识／版本／正文租户／拆列谱系和计数的负向测试。
- 独立 Prime 只读复审 PASS。
- 无共享迁移、真实业务写入或外部调用；无页面变更，不声称浏览器验收完成。

下一切片：SourceReadiness 本身的持久化精确引用入口，以及 DataFulfill 对真实 Hydration／Evidence／Readiness 的谱系核验。NiushopObservationBatch 的 FactRevision 不能与 PlatformObservation 名义互换；按231-6施工卡纠偏，不发明已完成事实。
