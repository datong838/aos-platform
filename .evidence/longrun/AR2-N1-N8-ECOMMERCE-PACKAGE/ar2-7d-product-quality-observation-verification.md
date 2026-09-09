# AR2-7D D1 保真商品质量观察验证

2026-09-09，基线93477f5f；仅m1与自有18434隔离PG，无真实源、Provider、发布或push，230 L0挂起。

- 新/旧观察、源投影、组合Evidence和旧Query四文件71 passed，4.43秒，/tmp/ar2-product-quality-observation-first.log。
- 配置观察（新旧spec均验证单次配置绑定及漂移在连接前拒绝）、原观察Evidence、旧JDBC源适配器、旧商品比较四文件43 passed，3.63秒，/tmp/ar2-product-quality-observation-neighbor.log。连接器均为替身，数据库仅隔离真PG，不代表真实源验收。
- 新spec保留软删/下架/0时间/缺字段/非法数值/重复ID原行；秘密额外字段排除；0/100/101与非有限数、跨site反例；严格spec/cleaning配对；旧比较与Query拒绝新规格。新Evidence写/read/revoke/rollback实际通过，仍factIds=[]，不保存原行。
- 本地独立只读复核无阻断项，非外部Prime。source_read_observation.py SHA-256 28eaa76dbb2c16eaf168d19ac68143d3c07e54339026f8acefb466d1151c11e2；ec_source_adapter.py ede0c5f0e888b5ccb6fe9f2596e79917bba7d7bfe4d6c27d03a45d63cc9e9a63；旧comparison a618415909b8ac96900864b1ede4e8c215286e0dc8ec04f86bc8312674799ff2；旧query 30dc667dda22ee2567cf4a32cd324ae1e24811d931d87caa94494c519c4c02d6。
- 闭包ar2-1扫描1702/分类88/迁移57，五类错误为空；diff --check通过。方案与实现一致，v1合法正文/哈希算法未变。
- 尚无联合质量测量、需求人口策略、真实源快照/连接身份或DataFulfill；AOS-000571保持、不推进整波GREEN。下一项基于新规格逐商品计量明确过滤、重复隔离、联合字段有效性，不能把三个边际数合成有效商品数。
