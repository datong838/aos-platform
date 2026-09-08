# AR2-7D D1 实际连接器读取观察切片

基线 df85926d / AOS-000571；沿用原 Task/Lease。只交付受控源读取的观察事实，不宣布采集权威或履约已闭合。

## 已查证缺口

`ec_source_adapter.fetch_source_rows` 返回裸列表；`ec_live_executor._stamp_snapshot_observation` 用运行开始时间形成部分对象版本。`ecom_ingest_receipt.created_at` 与 `projection_outbox.created_at` 均是本地落库时间。现有系统没有对象版本至独立实际读取区间的持久关联；不改名借用，不回填历史。

## 本切片最小实现

- 新增 `services/aos-api/aos_api/source_read_observation.py`，提供不可变观察正文：租户、sourceId、实际执行的非秘密查询描述、连接器读取开始/结束区间、取回/清洗排除/保留数量、清洗后批次摘要、清洗规则版本。上游快照时间未知，source配置未有exact版本，该两个字段明确为空；不得构造伪引用或认定可履约。
- 修改 `services/aos-api/aos_api/ec_source_adapter.py`，新增显式 `fetch_source_rows_observed` 入口，复用既有 meta_source 与 JDBC 只读权限路径。旧 `fetch_source_rows` 及 live executor 不切换，旧运行行为不变。新入口只接受单次无游标、带非空店铺等值过滤的完整有界查询；固定取101行，最多接受100行，超限直接拒绝，不能采样后成功。
- 时钟由宿主在 `read_rows` 紧邻前后读取，失败不返回观察。连接建立时间、运行开始时间、后续清洗时间均不伪作查询时间。时钟倒退/无时区拒绝。不宣称远端业务历史快照、跨表一致性或数据最新。
- 清洗调用既有规则；只对已清洗结果生成规范JSON摘要，不保存原始PII、连接配置或凭证。字典顺序无关，行顺序保留；支持JSON基本类型与有时区datetime、有限Decimal，编码有类型标记防止字符串碰撞；未知类型和NaN拒绝。返回正文与行列表分离，调用方可复验批次摘要，观察正文不包含行正文。
- 新增 `services/aos-api/tests/test_source_read_observation.py`、`tests/test_ec_source_observation.py`；测试使用受控内存JDBC替身，不建立任何真实连接。验证实际时钟包围读取、失败不出结果、101超限、空集、软删和PII清洗、无scope/source/过滤/游标拒绝、摘要漂移及时间和类型边界。

## 下一步与门限

独立设计复核收紧：首版仅固定 `niushop.product-observation/v1`，表必须为 `ns_goods`，过滤只允许单一正整数 `site_id`，不接受任意等值字段或额外条件。公开字段固定为 goods_id/site_id/goods_name/price/goods_stock/state/is_delete/modify_time/create_time；原 `_clean_rows` 不能作为通用脱敏证明，故先按此字段集合投影，再复用零时间及软删规则。调用清洗时不传pipeline/node标识，不改写既有全局DLQ计数。未知规格、表/店铺范围不匹配和分页均拒绝。

后续须有不可变存储、源配置exact版本、清洗后行至归一化对象版本的同事务映射及重放回读，再允许固定质量查询读取。当前观察仅为尚未持久化的本次调用结果，不注册为DataFulfill、不更新历史对象、不启动真实采集、不执行共享迁移。
