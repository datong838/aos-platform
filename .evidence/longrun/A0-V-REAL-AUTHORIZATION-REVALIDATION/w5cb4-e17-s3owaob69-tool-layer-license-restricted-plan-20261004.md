# b69 文件级方案：Tool 两层权威与 License 受限事务首接线

## 先读方案后纠错

- W-D3（92）明确 `requiredToolRefs`/`toolDependencyRefs` 10/10 是 frozen `EvidenceBundleRevision` exact projection；代码 `aip_capability_tool_deps.py` 同样固定此 assetType，`exact_assets_available` 校验 revision/hash/frozen/revoke。b68 初版仅看 `aip_tool_binding` 而称 Tool 无真源是错误结论，已作追溯修正。
- W-L20（128）`aip_tool_binding` 属实例执行分配，要求绑定 agent_instance_id、active status、解析 Receipt，不能用定义级 Tool ✓ 代替实例运行准入。b69 不新建 ToolRevision 表、不修改当前库。
- b67 signed Growth1.13 isolated 受限 SQL 命令已锁 Installation/Registry 并完成 blocked Binding↔Receipt 配对。b68 只在 owner 连接证明 License Evidence `for_transaction` 可见性；受限 definer 尚无该表 SELECT/RLS。

## 最小施工

1. 在 `services/aos-api/tests/extension_runtime/plan_restricted_evaluate_case.py` 的 signed full-schema 夹具新增 opt-in License 源检查；`test_growth_signed_installation_full_schema_pg.py` 仅传模式开关。测试专用 frozen EvidenceBundle 使用真实 schema、固定 id/revision/hash、非空 license_summary；命令内部 trusted SQL 读 exact row 与 revoke event，调用方不传 hash/结果/GUC 作为授权事实。
2. RED：在 definer 没有 Evidence/撤销表 SELECT 时受限命令 42501，Binding/Receipt 0；再只给 definer 最小 SELECT 和 tenant RLS，原 signed blocked 命令成功。随后 committed revoke 后再调用必须拒绝，Binding version/Receipt 不增加。复核 dev-org/旧 key/撤销竞争负门。
3. 继续 blocked：单一 License 证明不代表 Provider/Route/Policy/Eval/Data/Tool/Budget 全齐；尤其 W-L20 实例 ToolBinding 运行门及当前正式凭证未证明。若无法按现有锁序防并发撤销，本波只称事务快照可见性，不称 available 正向。

## 复审边界

本波的撤销负例是已提交 revoke event 后再次调用。测试没有把 revoke writer 与受限命令绑定到同一锁序，因此不能外推为并发撤销线性化或正式发行可用。定义级 Tool exact ref 与实例级 ToolBinding 仍按 W-D3/W-L20 分开评估。

## 安全边界

仅 disposable `aos_test_*_ti4_test` 与本地签名 Growth1.13/隔离 OCI；真库135只读，Host/worker/Provider关，不读商城源、不回放旧Run、不手工run_definition、不碰230 L0、不push。正式唯一136/当前实例 GRANT 另波，需要新备份、全恢复和零执行窗口。
