# 独立完整root快照非授权传输

基线AOS-001404 / m1@e64591bc，沿原root-snapshot-registration-contract及原FileTrustRootProvider安全快照语义。候选一：完整非授权传输与整hash（本轮）；候选二：root正式注册152，需要独立迁移scope/实际部署anchor/权限和完整登记原生负门。只完成一，不替代二。

文件publication_contracts.py、test_provider_capacity_publication_pg.py及本目录，均原publication Task scope。新增freeze_capacity_trust_root_snapshot(exact FileTrustRootProvider)，只调用一次原snapshot完整安全读取，不另开文件、不截断、不缓存，复用原FrozenTrustRootProvider不可变_roots映射（内部接口，显式记录耦合）。输出frozen dataclass的canonical_bytes/content_hash/root_count，固定ROOT_SNAPSHOT_TRANSPORT_ONLY_NO_TRUST_NO_REGISTRATION，无verified/key注册/执行许可。

独立协议aos-capacity-root-snapshot/v1：JSON恰trustRoots；原每根8字段全部保留，按(publisher,keyId)排序，字串ASCII JSON转义、sort_keys/紧凑分隔，公钥由原验证后的32bytes标准base64、时间用原aware datetime.isoformat保持偏移和瞬时值，revokedAt nullable。不套signed-body UTF8/1000/200门。原File允许240字符/内部空格，甚至转义的孤立surrogate；完整快照作为opaque ASCII bytes/hash必须保留，当前不能将整文档转PG JSONB或直接把它当签名文档。正式使用root仍需独立授权以及精确主体/取钥校验。

输入原文件1MiB/10000限制由原安全reader执行；输出另门8MiB。ASCII escape最坏每输入字节扩至6字节，时间归一每根最多3*48新增字节，10000根保守上界6MiB+1.44MB<8MiB；一般输出更小。无canonical_json签名文档函数重用，避免surrogate或控制字符合法root被意外丢弃。该bounds推导必须有大unicode/control实际接受域测试，不能空口保证全生产实现。

先新入口缺失RED；1001根、240/空格、Unicode/surrogate/control、原带秒微秒offset、year1+23:59边界、撤回/非标准有效base64、排列/空白稳定hash、root/key/revocation变更hash变化、原拒绝duplicate/symlink，以及非原provider拒绝。输出不能伪造注册。专项及publication/原signature相邻，证据精确hash/复审/提交/上下文；无真库/DDL，原Task ACTIVE。

首扩充专项1failed/6passed/5.86s：误认为原FileReader检查0666模式，实测该接口没有此门。改为原非普通文件拒绝，另记录0666也仅产生非信任transport；不改共享reader、不把安全读取文件形状等同受控安装配置。正式anchor/配置写者权限与scope门仍必需。
