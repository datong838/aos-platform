# AR2-7D D1 读取观察持久化施工卡

基线94159d35；AOS-000571，同一Task/Lease。新增 `services/aos-api/aos_api/source_read_observation_evidence.py` 和 `services/aos-api/tests/test_source_read_observation_evidence.py`，复用原 `aip_evidence`/撤销表，不新增迁移。

- 宿主先对实际读取返回的行和观察复验摘要，再以完整观察正文＋规范actor构成内容地址，Evidence ID使用独立前缀。只保存观察元数据和行摘要，不保存行正文或凭证；factIds固定空，不提供经营事实覆盖。
- Store仅接收HostTransaction和TenantScope，不自行commit。put必须复核租户、完整typed正文和行摘要，插入后同事务read_exact逐列核验。相同body/actor返回原Evidence；失败由外层rollback；恢复只按已知exact ref回读，不调用连接器。
- 表中`observed_at`为读取结束，`freshness_at`为该读取事件的开始，只描述观察事件；不得转为上游数据新鲜度。源配置exact引用/上游快照仍为null，source_ref只保存现有sourceId，subject_ref为该source的非版本化定位，不制造SourceRevision。
- created_at由数据库记录实际入库时钟，不进入内容地址，回读要求有时区且不早于读取结束；该字段不作为业务授权。完整观察区间、计数、规格和行摘要全部进入内容地址。原immutable Evidence与撤销权威负责防篡改和失效。
- 验收：跨租户、引用/hash/拆列漂移、撤销、metadata或行摘要篡改、相同正文重放、不包含行正文、零fact覆盖、UTC等价、外层回滚；PG使用一次性隔离库。若数据库环境仍不可用，PG测试保留未验，不能封板完整DataFulfill。
- 独立复核修正：INSERT显式使用clock_timestamp()，不采用表默认NOW()（事务开始时间）。正文固定purpose=observation-only、upstreamFreshness=unknown；通用Evidence展示可能按freshness_at将读取事件标为FRESH，这不表示源数据新鲜。factIds=[]必须经真实通用覆盖器反证不能覆盖任何非空业务事实需求；不以说明文字替代该测试。
- 后续：源配置精确版本与归一化对象版本关联；历史对象不回填伪观察，不开放公开路由或真实采集，不push。
