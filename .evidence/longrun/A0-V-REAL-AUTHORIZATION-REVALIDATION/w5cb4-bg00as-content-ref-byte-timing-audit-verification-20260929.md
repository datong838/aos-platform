# W5CB4 BG-00as｜content_ref→S3 字节读回时机审查

方案：`w5cb4-bg00as-content-ref-byte-timing-audit-plan-20260929.md`。本波只读；没有写当前库、读取对象或改运行入口。

1. `aip_eval_authority_store._assert_artifact_snapshot_source` 仅要求 source/redaction 两条 `content_ref` 为非空字符串。`test_aip_eval_pack_registry.py` 的正向注册使用 `object://isolated/...`，`test_aip_skill_publication_service.py` 使用 `test-only://...`，BG-00aq 隔离 writer 正向也使用 `object://test-only/...`。这些测试覆盖元数据合同，不证明 content_ref 已是 S3 key。现有 Store/Writer 不返回/传递规范对象 key 给有界 reader。
2. `aip_eval_object_reader.read_verified_eval_object` 接受的 key 必须是 `org/project/evals/`，它经 `object_store.get_bytes(key,max_bytes=2MiB)` 读对象。与目前可登记的 URI-like `content_ref` 没有已批准映射规则；直接把它当 key 既会拒绝现有正向行为，也没有真实 G2 producer 提供规范 key。读取应先有 Owner 冻结 schema/key/不可变性、redaction 签发/撤销和失败回滚合同，不能在 serializable DB 事务内凭猜测加网络 GET。
3. 当前正租户 Eval Dataset/相关 Artifact 0、正式 writer role0，固定 MinIO 镜像与19000服务缺。当前签名 G2 Eval 文件仍 BLOCKED placeholder。没有真实对象字节正向，也无法用 test-only 注入 reader 代替业务验收。

判定：BG-00as 未改 Store 或 Writer 的合法旧合同；下一波转 231 首链 E03/BG-00 最小配置来源/绑定产品链只读盘点，找与正式 Eval source 独立的最小点，按先方案后 RED/实现。Eval S3 字节门待正式 G2 source/object/redaction authority 和可用存储后再接。Host/worker/Provider/首链继续禁入。
