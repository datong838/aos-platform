# W5CB4 BG-00j Artifact snapshot 来源元数据前检方案

先复习 231-1/5/9、栖月汇全店经营方案、AIP-4 E1A/B 与 BG-00i。当前栖月汇 `aip_artifact`/脱敏 Receipt/Dataset/Suite 全 0，不能制造正式来源。

## 文件级施工

- `services/aos-api/aos_api/aip_eval_pack_registry.py`：在既有 Registry 增只读 `inspect_artifact_snapshot_source(scope, manifest)`，仅支持 `artifact_snapshot`；在同一 scoped PostgreSQL 连接查 `aip_artifact` 的 source 和 redaction Receipt 精确身份/type/hash。source revision 与 receipt revision 只接受该表无版本列所代表的 `1`。禁止返回内容、metadata、content_ref、source 字段。
- `services/aos-api/tests/aip/test_aip_eval_pack_registry.py`：隔离 schema 的真实 PG RED/GREEN，覆盖同租户精确匹配、缺 source/receipt、错 hash/type/revision、跨租户、无字段白名单。只验证元数据存在与精确引用，绝不把成功前检当成已脱敏或数据集合法注册。

不改迁移、当前真实库、旧注册 API、Runner/ReleaseGate/Provider/Host。前检是合法来源开发的必要负向门；实际字段内容、脱敏过程/Receipt 签发、Judge/Target executor 仍须后续正式 Owner 验证。专项/相邻回归、编译、diff check、当前库只读缺源反证后 verification 落盘与精确提交。
