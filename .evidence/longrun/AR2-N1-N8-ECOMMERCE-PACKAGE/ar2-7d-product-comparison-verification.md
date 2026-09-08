# AR2-7D D1 商品观察与规范版本比较验证

- 基线00494ba4/AOS-000571，m1同一Task/Lease。新增固定只读ProductObservationComparisonReader及专项测试；两个既有规范读取器仅public限定，closure-manifest按实际data query port新增分类，未弱化验证器或preHash。
- 源行必须复验持久组合Evidence的原rows hash，重复/非法ID或错店铺拒绝。先read_bound核对物理Shop，再读取完整有界Product集合；即使集合为空也核验店铺。
- 复核纠偏：实际ec_ot_writer固定niushop/site=1/external_id=niushop:1:{pk}，首版按此精确合同支持；不使用直接十进制ID或猜后缀。修改真实fixture先复现身份不匹配，再修正比较器。空集fixture初次未清excluded_count而触发合同失败，随后只修fixture，不放宽产品规则。
- 每个规范对象按完整六元身份+payload hash回读，使用原deterministic_hash字段结构重算原payload，含不共同对象；不经DTO补默认。各字段match/invalid/mismatch分区之和=common_count，source/canonical总体均包含仅一侧存在项。只返回统计与exact refs，不返回properties；不造FactRevision、写入Receipt或质量成功。
- 专项最终15 passed, 7 warnings in 4.91s；邻接人口/组合批次55 passed加1个夹具失败，该失败已修并由最终专项覆盖。店铺选择7 passed。描述PG原默认9 skipped，不记通过；转临时实例初遇并行迁移ALTER ROLE冲突、随后发现pytest模块重载未采用预导入替换。改为收集阶段只对该模块注入本次18434配置并串行运行，最终9 passed, 7 warnings in 5.59s。旧18432未启动、未写入。
- 后续所有同实例PG测试串行启动：一次性数据库之间仍共享角色，不能并发迁移。该环境教训不通过放宽迁移或权限解决。
- 独立只读终审无阻断；实现SHA256 b441903de6eea7b6f001cb4d17d34a39f8d502ff7107db71179816a418b02c75。闭包ar2-1扫描1700/分类86/迁移57，五类错误零；diff --check通过。不是外部Prime PASS。
- 仍仅当前集合比较，不证明旧归一化由该观察生成、历史窗口、新鲜度或业务覆盖；后续需接实际QueryResultOwner与Requirement固定策略。无真实源/Provider/外部发布/push，230 L0挂起，D1及后续未封板。
