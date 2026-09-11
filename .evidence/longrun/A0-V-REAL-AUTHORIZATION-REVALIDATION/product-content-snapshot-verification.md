# 内部商品内容准备候选验证

2026-09-11，m1 8b169ab7，AOS-000573。新增ProductContentSnapshotReader，在同HostTransaction/Scope下先执行既有ConfiguredObservation/当前shop selection/原文hash和joint quality读取，再用同一八项逐行规则计算可准备商品。明确删除/下架过滤后重复ID全部隔离；仅八项有效且库存>0进入候选，库存降序/ID升序取前5，保留所有可准备商品总数。输出原始ID/标题/库存/原行hash，无价格文案/销量/收益预测或整体ready。旧质量规则抽取为共用函数，原政策版本和计数语义不变。

## 验证

先失败测试模块不存在。隔离fixture初次缺aos.org_id/project_id被既有SourceConfiguration触发器拒绝，补正确scoped连接设置，未停用约束。最终54项相关测试通过：新商品文件19项（12项商品场景+7项既有quality回归定向在一次性克隆运行）、方法19项、QueryEvidence16项。包括全量8→展示5、重复过滤/空/无效字段仍在分母、错scope/原文漂移、稳定排序、超大库存/超长标题拒绝、旧joint quality同边际不同联合有效数/撤销/快照隔离/布尔引用/时钟回归。7条既有警告，退出0，退出后既有JDBC日志流关闭错误。

## 限制与下一步

本波计算未持久化、未接宿主或生成Task，来源来自合成数据库夹具，未执行真实经营。完整观察仍最多100行，不把Top5候选当全量样本；99规范对象规模限制未改。主库只读目标scope当前active规范对象清册为空，不能解释为真实店铺商品数为0。无Provider/主库写入/API重载。

下一波：可恢复的原文与商品候选快照Evidence，保留完整类型/hash、质量/口径/来源及当前撤销与披露；随后正式Metric/Query/D01和内容任务宿主接续，真实源恢复后执行业务首链、八场景和观察。不push，230 L0挂起。
