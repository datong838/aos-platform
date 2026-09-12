# 商品快照显式转换 v2

2026-09-13，0e22e375，主A0-V Lease；本波不生成/发布包、不改当前安装、不读取源数据。P01已通过真实单次接入，P02/P03尚无正式图，现有转换v1仅string/int/timestamp且source_updated_at使用观测时间，因此不能直接宣布商品变化链已就绪。

新增 services/aos-api/aos_api/pipeline_snapshot_materialization_v2.py，修改 pipeline_snapshot_materialization.py 仅按明确schema版本委派，新增 tests/test_pipeline_snapshot_materialization_v2.py。v1合同和已有P01候选不改。v2复用v1固定字段、租户过滤、唯一键、required、defaults校验；只增加decimal/text以及显式源时间、删除、状态解释，不执行代码或任意表达式。

v2配置沿用五个基础字段，额外且必需：source_updated_at={primary,fallback}（均已选timestamp字段，primary为0才使用fallback；两个均无有效时间拒绝，不用观测时间伪造源更新）；tombstone={field,live_value,deleted_value}（已选int，值必须不同；未知值拒绝）；status={field,values}（已选int，字符串十进制键映射固定可打印大写raw枚举；未知值拒绝；删除覆盖为DELETED）。source_updated_at晚于observed_at拒绝。源时间变化和观察时间分离，使未变化商品的权威记录不会仅因轮询时间而变化。

decimal只收Decimal或严格int，有限值、最多38有效位、小数最多18位、整数最多38位，保留十进制字符串进入已有canonical JSON（与Core模型Decimal编码一致），拒绝float/字符串/bool/NaN/Infinity和越界。text仅原始字符串且最多262144字符，不执行/解析HTML。所有数据校验整体完成才能返回，错误固定码且无正文。

v2第一切片是Product对象；任何非空links声明暂时明确拒绝，不能静默漏掉ProductSku→Product关系。P03在后续声明化链接合同完成后接入，不能假定与P02同时完成。未实现空结果推断硬删除；仅显式is_delete事实可产生tombstone，之后的候选映射必须读取site内完整状态范围，不能goods_state=1过滤后假装下架已同步。

验证：v1所有既有测试保持；v2金额精度/文本、源时间优先与fallback、两次不同观测时间同一源更新一致、删除/上下架状态、未知状态/坏时间/额外字段/float和非有限小数/重复主键/未声明链接拒绝；输出经既有_normalize_rows进入canonical对象并保留tombstone。随后检查SourceSelection、controlled executor相关回归与闭包。下一波才物化新候选、进行Schema实证与正式图/审批，不能修改已签名1.4目录。

首次核验1 failed/55 passed：canonical Product要求shopId/title/categoryId/status，不能用旧字段name/siteId代替。测试输入显式映射这三项；status声明增加必需property_target，向该属性写同一已声明raw状态（删除为DELETED），禁止覆盖既有映射或defaults。属性状态不从常量填充、不隐式改变大小写，后续候选需对齐既有消费语义。该属性名由签名mapping声明，不能由HTTP临时指定。
