# W5CB4 BG-00l｜当前 D01 Eval 来源生产者与签发权威只读审计

基线 `aos-platform/m1@1739f351`、权威 `AOS-000860`。复习 `231` 首链、`228` G2、AIP-4 E1A 与 `40-...EvalPackRegistry对账.md`：真实来源 reference/hash、字段 allowlist、脱敏 Receipt、case count 为正式 Dataset 条件；Mock/synthetic/demo 与内联业务行不得用作验收。

1. 当前签名增长包 `solution.ecommerce.growth/1.11.0/content/evals/placeholder.json` 原文 `status=BLOCKED`、`reason=Waiting for G2 review`、`note=Growth evals are produced by G2, not by D-wave`；`shasum -a 256` 为 `e90c23c9234793da6f76f82cc78ceddd677ce47c4c6ed7ced8397bb11d0a69c2`。签名 Receipt `outcome=SIGNED_TREE_GREEN`，`signedTreeHash=sha256:b6aa0dbd0c9d720a8167349d90a9dfbc48b3c689aa4a1746a654aeaa9e0d144d`。签名成立不等于 Eval 放行。
2. `rg -n 'eval_dataset_snapshot|redaction_receipt' services/aos-api/aos_api --glob '*.py'` 的 16 个匹配只覆盖合同、BG-00k 只读引用门、隔离内容样例、其他领域收据字段；没有当前 D01 `eval_dataset_snapshot` 与 Eval 用 `redaction_receipt` 的正式生产 Owner。`aip_artifact` 通用表有 `content_ref/source/metadata/marking/content_hash/created_by`，但通用 `AipTaskStore` 可写并不构成 Eval 来源生产者或脱敏签发。
3. `business_investigation_redaction_receipt` 是生意探究数据处理绑定下的独立不可变表，`content_hash` 带 `sha256:` 前缀、`status=safe/quarantined/blocked/unknown`，它不是当前 Eval `ArtifactRef` 的签发合同；没有发现 D01 到该收据的正式映射或授权，不能直接套用。
4. `AipEvalRunner.run` 的 `resolve_artifact`、`execute_target`、`execute_judge` 仍是调用方回调；`JudgeRevisionRef` 是合同引用。当前生产接线中没有 D01 的独立 Judge/Target executor Owner。BG-00i 同日 `BEGIN READ ONLY` 已证明栖月汇 Artifact/Receipt/Dataset/Suite/Run/Report/Gate/Event 为 0，BG-00k 没有当前库写入，故本波不重复造数据或执行 Eval。

结论：当前 D01 正式来源 RED，属于明确的 G2 产物/签发权威缺口；元数据门仍守住无来源登记。下一波需先冻结 G2→AIP Eval 的 exact 包身份、Artifact 内容存储、允许字段/脱敏签发 Owner、撤销与回读合同，独立隔离验证合法与非法来源；Judge/Target executor 另设精确权威。可并行做不依赖当前来源的负向门，但不能用旧 Logic dry-run、内容样例、调查收据或测试行解锁当前 D01。当前 DB 只读、Host/worker/Provider 关闭，首链未完成。
