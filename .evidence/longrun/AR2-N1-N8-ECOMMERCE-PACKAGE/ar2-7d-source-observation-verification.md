# AR2-7D D1 连接器读取观察验证

- 基线 df85926d / AOS-000571，同一 Task/Lease。方案见 ar2-7d-source-observation-plan.md；原 ec_source_adapter.py preHash=49310d77902c8cfa1dd0ba64afa5f22dc01df55d49b5ac5ceff7d1b45f452d6b。
- 新增实际读取观察入口，仅接受固定商品规格、单一正整数店铺过滤、无游标；取101行且清洗前超100拒绝。公开字段白名单先于既有软删/零时间清洗，不写全局DLQ计数；记录紧邻读取的开始/结束时间。旧 fetch_source_rows 与 live executor 函数未改。
- Red：观察模块缺失、观察时钟/入口缺失；独立终审发现公共DTO可变，新增顶层/嵌套赋值反例复现失败后，仅冻结新观察与专用tenant模型。未改公共TenantContext。
- 最终五文件专项/直接邻接 `--noconftest`：**54 passed, 8 warnings in 7.13s**。包括完整边界、清洗隔离、实际时钟顺序、空集/超限、缺租户/源/规格、错误范围、倒退时钟、非法类型、类型安全摘要、摘要漂移与不可变正文。
- 更宽旧 live 测试尝试为 **3 failed, 41 passed**：三项端到端依赖数据库，5433未运行导致 OperationalError/PIPELINE_EXECUTOR_FAILED；不计作通过，不将其伪归于新入口。未为过测改写旧测试或启动共享环境。
- 独立只读复审修复后无剩余阻断问题。source_read_observation.py SHA256=aa62a12981efa2cade92e2c5e77102f2ee91a7c9b779be44cd1e89bffa459e83；ec_source_adapter.py SHA256=13b5816373a7dd6069cb137011a860af3b34db9a8a6555cec58839ad0c5cec8b。非外部Prime服务回读。
- `verify_closure.py --phase ar2-1`：1695模块、85分类、57迁移，五类错误为空；diff check GREEN。既有schema/非法输入序列化警告和退出JDBC日志错误保留。
- **限制**：本次读取测试全为内存替身；没有真实源查询、持久观察、源配置exact版本、对象版本关联或质量履约。配置引用/上游快照仅允许null。新入口未注册为DataFulfill，AR2-7D仍未封板。
- 下一项：复用现有不可变Evidence存储，持久化观察正文并同事务精确回读；继续补源配置版本与对象归一化关联。历史采集依据缺失保持缺失，不用入库时间/运行时间回填。
