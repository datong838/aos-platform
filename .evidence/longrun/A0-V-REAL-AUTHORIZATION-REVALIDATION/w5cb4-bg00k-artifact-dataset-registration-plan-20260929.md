# W5CB4 BG-00k｜Artifact snapshot Eval Dataset 同事务来源门

## 上位方案与当前事实

- 231 首链、231-5/9、栖月汇经营产品方案要求正式证据与评测来源；AIP-4 E1A 要求 Dataset manifest 的真实来源、字段白名单、脱敏 Receipt、case count。当前 D01 evaluated，正式 Dataset/Suite/Run/Report/Gate/Event 及 Artifact/Receipt 均为 0。
- 当前签名增长包 `content/evals/placeholder.json` 明确 `BLOCKED`、等待 G2；历史 `aip_data_advisor_logic.py` 六项是隔离 Logic dry-run，不能作为当前 Skill 正式来源。
- BG-00j 的只读 `inspect_artifact_snapshot_source` 尚未接到 `register_dataset_revision`，存在先检后写或完全跳过的入口。当前 `a0v_111` 只读核验 `aip_artifact` 的 append-only 与 truncate guard 触发器均 enabled，`aos_runtime` 无 UPDATE/DELETE 权限；栖月汇 0 行。

## 精确文件与 RED

1. `services/aos-api/aos_api/aip_eval_authority_store.py`：在原 `create_dataset_revision` 同一 scoped 事务内，对 `sourceKind=artifact_snapshot` 解析严格 Manifest，并从 `aip_artifact` 精确核验同租户、source/receipt ID、type/hash、revision=1，再插入不可变 Dataset。错误回滚，不由调用方先检查再写。其他 source kind 保持现有行为；它们并未因此取得正式来源证明。当前 `aos_runtime` 不能 UPDATE/DELETE 且 append-only trigger 已启用；相邻真实角色回归证明 `FOR SHARE` 需要被撤销的权限，因此只做普通 SELECT，不扩权。
2. `services/aos-api/aos_api/aip_eval_pack_registry.py`：现有只读 inspect 委托 Store 的同一核验函数，避免两份安全条件漂移；注册仍走原 Store。
3. `services/aos-api/tests/aip/test_aip_eval_pack_registry.py` 与 `test_aip_eval_authority_store.py`：先 RED 覆盖缺 Artifact/Receipt 不得注册、同租户精确正例、跨租户及错 type/hash/revision 拒绝、直调 Store 不能绕过、失败无 Dataset 行；隔离 PostgreSQL，当前真实库只读。
4. 相邻回归已发现隔离正例用 `artifact_snapshot`，却只填 manifest、没有持久化对应 source/receipt。仅在 `services/aos-api/tests/aip/test_aip_skill_publication_service.py`、`tests/extension_runtime/test_ecommerce_content_pre_review_eval.py` 与 `tests/extension_runtime/test_ecommerce_content_review_pending_pg.py` 的隔离 PG 夹具补 exact Artifact 元数据，使其继续验证原正式 Runner/发布链；不改变生产包或当前库。第三文件还保留交接时已有的人工返工审批链测试补强，并单独说明来源。三文件加入本波精确交付范围。

## 明确不声称

本波不生产 Artifact/Receipt、不检查 Artifact 内容或脱敏签发真实性、不建 Judge/Target executor、不运行 Eval 或发布 Skill，不对当前库写入。`artifact_snapshot` 仅有“同事务元数据引用”负向门；正式 G2 来源与脱敏签发及其他 source kind 须独立后续施工。专项/相邻回归、编译、diff check、方案复审、verification、m1 精确提交、上下文/D-waves 更新后进入下一波。
