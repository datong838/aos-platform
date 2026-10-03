# E17-s3o-w-al｜Capability EvidenceBundle 撤销门验证

## 上位与现时
复习 231-9、AIP-7 第22号、BIND-1 第31号与原 W2 ProductionContract Store。当前 ProviderInstance/Route 真库0，正式密钥和 OIDC 主体/Owner/健康/容量均未证明；仓内 approved Plugin 与历史 r7 不计当前来源。`BEGIN READ ONLY` 当前卷回读 `a0v_135|Provider0|Route0|EvidenceBundleRevoke0|正式受限reader角色0`，退出0；测试库残留0。当前实例继续禁入。

## RED 与最小实现
- 原 Binding Data/Tool `exact_assets_available` 只核 EvidenceBundle exact hash；表生命周期允许 `frozen|withdrawn|superseded`，原原证据撤销通过 `aip_evidence_bundle_revoke_event` 留 append-only 事件且旧 frozen 行仍在。
- 文件级 plan 先写，withdrawn/superseded RED 为 2 failed/1 passed（退出1）；追加原撤销事件 RED 为 1 failed（退出1）。
- 仅对 EvidenceBundle kind 在同一只读连接核 `lifecycle=frozen` 与同 tenant/exact `(bundle_id,revision,content_hash)` 不存在撤销事件。EvalDataset 无 lifecycle，保留 hash 合同。受限 readiness reader 精确表名单仅加原撤销表，必须具备租户 RLS/SELECT且无写权限；正式当前 role/ACL 尚未切换。无 migration/DTO/HTTP/外部效果。

## 新鲜验证
| 关口 | 输出 |
| --- | --- |
| 目标单元：frozen、withdrawn、superseded、显式撤销、EvalDataset 原路径 | 5 passed，退出0 |
| 可销毁 PG 原表/RLS 与受限 reader 相邻 | 8 passed，退出0；先 frozen 可用，exact revoke 后拒绝，错租户拒绝 |
| 全部相邻 Binding/Skill/受限 reader/PG | 29 passed，退出0，7 既有 warning |
| py_compile、diff check、三条动态 SQL pglast | 均退出0 |
| 可销毁测试库残留 | 0，退出0 |

复审：这是 Binding readiness 只读失败封闭加强，未赋予任何发行权限；当前正式 Provider/Tool/六 Binding/八配置仍缺，不能计首链。新生产代码需在原卷 PG→API→Web 质量门加载后另证；独立全备的全库恢复演练仍未做。
