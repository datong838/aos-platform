# Invalid growth 1.4 正式退役验证

日期：2026-09-12

## 结论

- 隔离数据库先生成仓外恢复快照，随后从 `a0v_012` 升级到唯一 head `a0v_016`。
- 新迁移只允许从未激活的 `approved -> uninstalled`；数据库触发器要求零 Runtime Binding、零未终结 Runtime Operation，且所有历史 resource lease 均为 `released + observed_release=true`。
- 应用层 guard、数据库 trigger、完整历史领域模型使用同一迁移边界；uninstall Evidence 哈希显式包含真实 `fromState=approved`。
- 真实 Installation `c1eb714f-56de-4f28-ba06-c3440b3d18cb` 从 revision/etag 3 转为 4，状态为 `uninstalled`，activeRevision 始终为空。
- 首次命令 `replayed=false`，相同 idempotency key 第二次 `replayed=true`。正租户清洁计数全部为 0，负租户 Installation 为 0；Provider、业务 Operation 与外部发布均为 0。

## 自测

- evidence/store/uninstall/迁移组合回归：33 passed。
- Alembic 唯一 head：`a0v_016`；真实隔离库 upgrade 成功。
- `git diff --check` 通过。

## 证据

| 文件 | SHA-256 | 说明 |
|---|---|---|
| `invalid-growth-1.4-retirement/backup-summary.json` | `cacc6831b69ffe4945cd467d541b4f2c26055518979c558e251cc877e596ce0c` | 升级前仓外备份摘要，dump SHA-256 为 `322efe8d...` |
| `invalid-growth-1.4-retirement/uninstall-result.json` | `35f949cc3e07ec98a1f0fee3455e211b66819cc740567c906a9d7ac9ba468485` | 真实退役与幂等回放 Receipt |

数据库 dump 与凭据只留仓外；仓内证据不包含 DSN、密码或私钥。
