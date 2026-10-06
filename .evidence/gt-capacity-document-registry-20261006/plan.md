# 可信原文登记数据库边界

基线 AOS-001412 / m1 65adfeddf936b45897c7eaa6d8402af16d08e2a4。Task gt-capacity-document-registry-20261006，唯一原 thread owner，四精确 scope，期限 2026-10-07 12:00+08。新 a153 additive，不回改 a152 或已占用 a151，不触碰其他任务文件。原完整 Source、正式身份、签名撤回、最终 COMMIT 时效和自然首链保持未闭合。

## 依据与候选

231 首链/八工作台目标，原 publication 计划 27、47、82、84、115、119 行：独立 bootstrap authority、允许 policy/attestation/permit exactrefs、完整签名原文、稳定 root-policy epoch 与独立 publisher。R2a/R2b 已有根实际提交/回滚/重复/行锁及完整输入证据；不把它当 Source 发行完成。两个安全候选：完整受控原文登记；其后 Source consumer 当前性。后者依赖前者，选择登记。时间裁决 pending 不阻断此签名出处存储；没有当前 Source prepare/commit/消费入口。

## 文件与完整接口

新 module 实现 install_document_registry(execute) 和唯一私有入口 register_document(kind text, raw_body bytea, signature bytea) RETURNS text。kind 只接受 ProviderCapacitySourcePolicyRevision、SupplierCapacityAttestationRevision、ProviderCapacitySigningPermitRevision，映射原 read_source_policy/read_supplier_attestation/read_signing_permit，保留全部原字段、literal、Unicode、canonical、整数和时间校验。函数不接自由公钥、verified、role、tenant、部署 expected DB、caller origin hash。新 a153 只安装本私有模块，不改变已有业务表/配置；down 禁止删除证据。

新签名原文表 document：双 scope 固定正向、content hash SHA256(raw)、kind/assetId/revision、raw 1..2MiB、64byte signature、origin hash/epoch、snapshot hash/root ordinal。revision 为原十进制文本（最大4300位），不偷偷缩为 bigint；identity 使用 C collation。内容 hash 主键和 kind/id/revision 唯一键，origin/root FK immediate、RLS ENABLE/FORCE、既有独立 OWNER positive 双 GUC policy。UPDATE/DELETE immutable trigger，PUBLIC/runtime/issuer/publisher 无表/列/sequence/helper权限。默认空、原两角色 NOLOGIN 不变。

SECURITY DEFINER 仅独立 publisher 可 EXEC，OWNER/search_path pg_catalog 固定；session_user 必须 publisher、双tenant GUC正向，publisher禁止 inherit/super/createdb/createrole/replication/bypass 和任何成员关系。私有 owner 为实际保留身份，不借原 License/Capa 角色。三个完整纯 parser 仅 OWNER 可用。不存在原生 C verifier则不接受；C catalog/schema owner/library/symbol/type/strict/immutable/nonSECDEF及独立 crypto owner flags/membership核对同原登记门，不安装扩展或放宽系统权限。

## 来源与顺序

只锁原稳定 registry_epoch FOR UPDATE，再原文/immutable anchor，不进入旧 guard/License/Capacity，不逆向锁原域。当前支持原登记 epoch1/head，缺行、失效 epoch 或空 head拒绝，不自行恢复撤回。数据库加载当前 origin 原 body/signature、bootstrap profile、anchor：重新核 SHA256、签名、anchor revision/publisher/key/subject、bootstrap/current clock、actual current_database/OID/cluster 及受控安装 target；host/port不从服务容器映射反推。

从完整文档推导 assetType/assetId/revision/contentHash，必须完全在当前 bootstrap allowedDocumentRefs 中（不是只名字或 hash）。policy/permit 自身 deploymentTarget 必须与受控 anchor/native部署匹配；supplier attestation 无 target字段，以 bootstrap exact签署允许+本库 origin provenance绑定，禁止虚构新字段改变原协议。

公钥仅从当前 snapshot 的已派生 root_entry 取；publisher/key 字符串逐 Unicode codepoint 精确匹配 root codepoints，不能拿 caller key或准许文档自己的 signerPublicKey 验自身签名。当前时间须位于 signer根及文档有效窗口，根 revokedAt 已到拒绝；原 C 对完整 raw bytes 验 Ed25519，原始签名不经 JSONB重签。保存全部 raw/hash/signature/root/origin provenance。注册只证明独立 authority签署准许此原文；policy-attestation配对、Source signer permit许可、Provider/Evidence事实、撤回和执行由后继完整 issuer/consumer逐项核，不能用登记 PASS替代。

已知同 hash重复只在所有原文、signature、kind/identity及当前 origin/root provenance相符时回读，不改变 epoch、不新增第二版。同 identity另一原文/签名不能静默覆盖。INSERT与实际 caller COMMIT/ROLLBACK原子；返回前再核有效窗口，过期异常回滚，但明确不是 caller 最终 COMMIT TTL保证。未知返回/断联只读按原 hash对账，不重发。

## 验收与退出

从固定 test-only none-network256MiB native C实例模板创建唯一随机新库，复用现有 committed_native_registry fixture并保留新库，受控 test-only签名 key仅内存。bootstrap真实签署批准三个完整文档 exactrefs和 root snapshot，先实际根 COMMIT；新模块缺失 RED。后继唯一 narrow publisher注册三类原文实际 COMMIT和第三连接回读原 bytes/signatures/refs/root/epoch；rollback全部为空，known replay只对账。

独立负例须分别把受控 bootstrap允许hash重签以排除“其他字段先拒绝”的遮罩：bad signature/未知根/撤销根/过期根/过期文档/错实际部署/未允许exactref/同identity漂移/root epoch失效/错误session/canary/直接表/helper写读。期望拒绝后独立行数和 epoch核对，正向真实角色通道不可由 fixture管理员保存记录替代。原 full parser、root R2a/R2b、a152/原151撤回相邻累计验证；无页面变化不冒充浏览器验收。最后源码和方案复审、hash/日志/精确m1提交、AOS/Prime同步。只有上述本范围全部通过才有 scoped Delivery，原完整 Source与root签名撤回/正式安装任务不因此退出。

Review additions: independent bootstrap-signed exact assetId/revision/kind mismatches beyond hash; document registrar-first/writer-first actual pg_blocking_pids and COMMIT coordination (Root-only competition is not substituted). Negative proof labels distinguish deliberately invalid signature or allowlist from other independent valid inputs. First cumulative606 has605pass/1 planned private document inventory compatibility failure; original Root Task records its own minimal exact-inventory test repair, not this Task scope expansion.

Complete-domain review: original revision accepts4300 digits; exact plain-text B-tree unique identity may exceed PG index tuple limit. Add actual native signed/allowed policy with deterministic noncompressible4300-digit revision before scoped completion. Do not narrow original accepted revision or replace it with bigint. If RED, enforce exact identity uniqueness via bounded DB-derived domain-separated SHA256 identity index, preserve full identity/raw bytes and CHECK recomputation; no caller-derived hash or truncation.

Identity drift acceptance: for each of policy/attestation/permit, independently sign two original documents with identical kind/assetId/revision and different validUntil, approve BOTH exact refs in the signed bootstrap, then register the first through publisher and actually COMMIT. Register the second through the same narrow channel; require physical unique violation, independent exact original raw/signature preservation and one row. This excludes signature/allowlist masking and checks that bounded identity indexing still prohibits overwrites. No formal database or execution permission is exercised.

Observed correction: green-r4 revealed original bootstrap rejects repeated kind/id/revision before root COMMIT; two same-identity approved refs are not a valid original protocol. Preserve this rejection and independently assert zero origin/document rows for all three kinds. Separately, after a legitimate publisher COMMIT, use administrative isolated-fixture INSERT of another fully signed canonical original with the same identity and different validUntil to exercise physical UNIQUE; require rejection and exact first bytes/signature/hash retained. Administrative constraint evidence is explicitly not allowlist or positive registration authority. No production gate is relaxed; green-r4 failures are preserved.
