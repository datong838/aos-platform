# W5CB4 BG-00an｜Skill Eval writer 来源绑定合同只读审查

方案：`w5cb4-bg00an-eval-source-binding-contract-audit-plan-20260929.md`。复习 228 G2.2、231/231-9、AIP-4 Eval 资产/Store/Runner、BG-00n/q 与当前 BG-00ak。签名增长包 `content/evals/placeholder.json` 是 G2 产品内容占位，AIP-4 真来源由 tenant Dataset manifest、Artifact snapshot/redaction Receipt、Suite case、Judge/Target 和 Run exact refs 组成；没有合同说把 G2 placeholder hash 直接绑定 issuer root `source_hash`，故未编码该臆造规则。

## 确切漏洞与证据

- `aip4_001_eval_lineage_observability_contract.py` 的 `aip_eval_run` 只有 tenant workspace FK，`suite_id/revision/hash`、`dataset_ref`、`judge_ref` 都是独立字段/JSON，无 Suite/Dataset FK。`aip4_002_eval_pack_registry.py` 的 Suite 表本身只 tenant FK；原 `AipEvalPackRegistry.register_suite_revision` 会先通过 `AipEvalAuthorityStore.get_dataset_revision` 对齐 Dataset，再写 Suite。`AipEvalAuthorityStore.create_dataset_revision` 对 artifact_snapshot source 会核 source/redaction Artifact metadata；`AipEvalRunner` 会经 registry 获取 canonical Suite。
- 当前 `aip_eval_writer_authority_preflight.py` 仅核 persisted succeeded Run 的 `suite_id/revision/hash` 与 Report，以及 Run 的 target/dataset/judge JSON 与 Report 一致；没有 SELECT `aip_eval_dataset_revision`、`aip_eval_suite_revision` 或 Suite case 集合。`test_aip_eval_writer_atomic.py` 已在 test-only 独立 LOGIN 下真签名成功提交 Receipt2/Report1/sidecar1；该 fixture 只 seed root/identity/Run，没有 seed Dataset/Suite。相邻累计69 passed 是机制测试，不等于来源门 GREEN。
- 事后独立只读 SQL：test-only `aos_bg00ad_schema_v2_20260929@a0v114` 和当前 `aos_current_preview_20260927@a0v114` 的 Dataset/Suite/Run/Receipt/Report/sidecar 六表逐表0；test-only 有专属 writer NOLOGIN role1，当前 role0。当前正式 G2/issuer/Owner/ACL/Host 仍缺，故漏洞尚未构成当前实例业务写入，但未来一旦接正式 writer，会允许一个仅具签名身份且伪造 Run 中来源引用的路径。

## 最小下一波 BG-00ao

先文件级方案与 RED：让 BG00aj writer preflight 在同一 serializable 事务 SELECT tenant 精确 Dataset/Suite persisted revision，核 source_hash/redaction policy、Suite canonical hash、target/dataset/judge refs、Suite case ID 和独立 input hash 与 Report 全 case 一致；缺任何实体、错租户/版本/hash/用例拒绝，再验签后写入。test-only 最小 ACL 只加两表 SELECT，保留无 INSERT/UPDATE；更新真签 fixture seed canonical Dataset/Suite，反向证明现有“无两表仍成功”变为拒绝。Artifact snapshot/redaction 字节/签发的当前性另核专门合同，不能把 Suite/Dataset 两行存在当作 G2 正式来源通过。当前库继续只读、Host/worker 关闭；不读取商城源或注入 placeholder。
