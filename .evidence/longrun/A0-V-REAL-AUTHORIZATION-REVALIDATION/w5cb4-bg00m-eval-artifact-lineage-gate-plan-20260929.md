# W5CB4 BG-00m｜Eval Artifact 内容地址与脱敏 Receipt 精确来源链门

## 方案复习与 RED

231 首链要求真实来源/可用产物；228 G2 的当前签名 `evals/placeholder.json` 仍 `BLOCKED`。AIP-4 E1A 要求 Dataset manifest 指向真实 source/hash、字段白名单、脱敏 Receipt 与 case count。BG-00k 只核 `aip_artifact` 的 tenant/ID/type/hash；测试中的两行空壳 Artifact 也能登记，尚未形成内容与签发来源链。`aip1_001` 已有 `aip_artifact.content_ref` 与 `source` JSONB，故本波不加迁移、不改当前业务库。

先在 `services/aos-api/tests/aip/test_aip_eval_pack_registry.py` 与 `test_aip_eval_authority_store.py` 写 RED：source/Receipt 缺非空 `content_ref`，或 Receipt 的 `sourceArtifactRef` 不精确等于 manifest source ID/type/revision/hash 时，Dataset 登记失败且无新行。跨租户、hash、revision 旧负例继续有效。

## 最小文件清单

1. `services/aos-api/aos_api/aip_eval_authority_store.py`：原同一 scoped 事务的两个 SELECT 加读 `content_ref/source`；只在 `artifact_snapshot` 分支要求 source/Receipt 地址非空，并要求 Receipt `source.sourceArtifactRef` 精确指向 `ArtifactRef(artifact_type=eval_dataset_snapshot, revision=1)`。读取元数据，不读业务正文，不扩大权限。
2. `services/aos-api/tests/aip/test_aip_eval_authority_store.py`、`test_aip_eval_pack_registry.py`：RED→GREEN、直调 Store 不可绕过、失败零 Dataset 行；正例只是隔离 PG 元数据，绝不作为当前 G2 内容真实或脱敏签发证明。
3. 三处既有隔离正例夹具 `tests/aip/test_aip_skill_publication_service.py`、`tests/extension_runtime/test_ecommerce_content_pre_review_eval.py`、`test_ecommerce_content_review_pending_pg.py` 补对应 `content_ref/sourceArtifactRef`，不改生产包或测试业务逻辑。原 RETURN Action `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED` 已知 RED 原样保留。

## 本波不声称与后续

非空地址和精确来源链仍不能证明地址的内容字节、hash、字段 allowlist、脱敏算法、Receipt 签发 Owner 或撤销。下一波必须接受控对象存储读回与正式 G2 producer/issuer；Judge/Target executor 另立权威。当前库只读、Host/worker/Provider 关闭，不读商城源、不重放旧 12 Run、不手工 run_definition、230 L0 挂起。专项与相邻回归、编译、diff check、复审、verification、m1 精确提交、D-waves/AOS/Prime 更新后进入下一波。
