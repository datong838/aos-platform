# E17-s3o-w-ao-b9｜License 证据撤销后绑定准入方案

## 上位方案与当前现场

复习 231-9 撤销后不得再执行、BIND-1 §3/`license_evidence_refs` exact evidence、W2 `aip_evidence_bundle_revoke_event` 与 b7/b8 禁入边界。当前原库 `org-org/dev-project` 的 EvalGate/EvalContract/EvidenceBundle/Revoke 行数 `0/0/0/0`（`BEGIN READ ONLY`、exit0），不造正式来源。原 `PostgresBindingDependencyAuthority.exact_assets_available` 对 frozen EvidenceBundle 查询 exact 撤销事件；同类 `license_evidence_available` 只看 frozen 与非空 `license_summary`，撤销后仍可能返回 true，导致 License 依赖继续计入可用。

## 文件级最小施工

1. 在 `services/aos-api/tests/aip/test_e17_s3oo_capability_reader_pg.py` 复用可销毁 test-only PG 与独立非 owner/NOINHERIT 只读 Reader，构造同租户 frozen 且含 license_summary 的 EvidenceBundle、错租户和 exact revoke 事件；先断言原 License reader 在撤销后应拒绝，取得 RED。再撤 Reader 对 revoke 表的 SELECT，证明连接预检失败封闭。无当前库写入。
2. 只改 `services/aos-api/aos_api/aip_binding_readiness_service.py` 的 `license_evidence_available`：用当前行 `content_hash` 查同租户、同 bundle/revision/hash 的 append-only 撤销事件；发现即 false。保留既有 ref 类型/整数修订、frozen/summary、空列表负例；不加新表、migration、公开 DTO 或自定义 License 权威。
3. 跑目标与相邻 readiness/Reader/Capability 测试；核产品方案一致性、跨租户、撤销后准入、撤 SELECT 失败关闭。API 代码若需 live 宣称，先按原卷 PG→API→Web 完整重启及浏览器只读复验；本波不把隔离 License 正向冒充当前实例，Host/worker/Provider仍关。

风险：撤销事件与 EvidenceBundle 生命周期可并发变化，本切片只修评估时的已撤销漏判；激活/执行时重新校验由原绑定/Host 门承担，需相邻回归确认。`org-org/dev-project` 唯一正向，dev-org 零副作用；不读商城源、不重放旧12 Run、不手工 Run、不碰230 L0、不 push。
