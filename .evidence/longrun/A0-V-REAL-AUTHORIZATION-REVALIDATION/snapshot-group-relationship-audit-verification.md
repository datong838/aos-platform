### SC4-5h5 当前已出现行关系残留核验验证

新增原Store有界 read_active_links_for_rows，强制exact scope/明确非空行集合、双端tenant/shop、<=32规则/<1000 IDs、最多24000活跃关系，空集合绝不扩大查询。新增PipelineSnapshotGroupRelationshipAudit，原当前命令/全部对象及候选投影核验后，按包rowType/direction只查本次出现行，比较规范candidate identities；旧关系仅列发现，未删除。引用缺失/非法/父对象缺失及比本次source观察更晚的额外关系列为unresolvedExtras；完整引用且非更新关系列为cleanupCandidates，但尚无删除执行或策略授权。前后有界读取比较且回调hash/current Owner复核。

58项组合测试通过35.78秒（Store51+新PG7）；新增缺父引用场景首次测试误解析empty parent的null command，修正夹具筛选后单例通过8.21秒，当前新PG覆盖8项。真实隔离库验证正确边无残留；旧父边只报告不删；未出现子行和tombstone边排除；新于快照的关系保留不确定；父对象缺失时额外边不得被列为清退；回调篡改/撤权拒绝、跨workspace/shop空结果、超界拒绝。源调用均一次。

AR2扫描1923/187/93五类错误为空，AOS-000573 memory-validate GREEN。主库和真实关系未改。当前发现不等于业务质量绿色。下一波：在领域包规则中明确选择性启用present-row清退语义，旧v1保持候选关系语义；随后固定原残留payload的清退命令及原严格Store/投影恢复，禁止缺行推断和清退较新关系。
