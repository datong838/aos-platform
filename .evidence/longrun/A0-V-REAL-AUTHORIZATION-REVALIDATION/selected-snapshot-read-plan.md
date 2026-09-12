# 显式选列的版本绑定快照读取

基线7054e061，2026-09-12。现有 ec_source_adapter 的版本读取仍走 SELECT *、无游标时无行数上限；不能用于新批准的 SourceSelection。新增 services/aos-api/aos_api/pipeline_selected_snapshot.py 与 tests/test_pipeline_selected_snapshot.py，不改变旧调用行为；新入口只由后续当前执行 Owner 调用，输入规格不是权限凭据。

1. 只接受 TenantScope、HostTransaction、严格 SourceSelectionDraft 和 MappingReadSpec。重新构造不可变规格，草稿当前有效；调用者保持当前执行事务及权限锁。锁 public.meta_source 当前行，按同事务 SourceConfigurationRevisionStore 读取当前配置；exact ref、源类型/状态/direct 必须一致，禁止传连接串或缓存连接。
2. 使用 normalize_source_connection_config 及 JdbcConnectorRuntime(reuse_cache=False)，单次 read_rows 只请求明确 columns、where_equals、1..1000 limit，不带增量游标、不自动重试。连接秘密仅传连接器，异常统一固定代码，不输出源行/驱动异常。
3. 返回数必须严格小于 limit。等于 limit 即拒绝为可能截断，不额外多读一行突破预算；即使实际刚好完整也保守拒绝，后续可用独立批准的分页/完整性设计改进。行必须完整匹配所选字段，主键非空且唯一，已选过滤列值一致；未满足不返回部分数据。
4. 测量连接及读取实际耗时，超过 draft.timeout_seconds 或结束超过有效窗口则不返回结果。现有驱动连接/读 socket 超时为30秒；本步骤的更短时限是结果接纳截止，不声称能按更短时限强制终止驱动。若需硬中断，必须另加连接器实现与真实验收。单次读取不证明多表一致快照、源历史时刻、实时Schema或存储引擎。
5. 输出仅为读取结果和实际起止时间/源配置引用，不记 Receipt、不写Dataset/对象、不生成运行，也不能替代执行前后的当前权限重验。与管道控制接线前仍禁用P01。

先验证版本漂移在连接前拒绝、源端columns与范围/limit固定、截断/缺字段/重复主键/范围异常/超时/连接异常均拒绝并关闭私有连接。再回归已有JDBC选列、私有连接清理与源适配器。真实源验收安排在当前审批/持久控制完整接线之后，不能用单元测试代替。
