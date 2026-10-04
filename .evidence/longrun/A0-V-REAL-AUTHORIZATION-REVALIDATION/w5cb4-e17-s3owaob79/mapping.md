# b79 当前来源映射与生产落点修正

代码7b0626ec，官方authority AOS-001329。实际Alembic ScriptDirectory.get_heads()输出唯一a0v_135；a0v_135_extension_schema_acl.py仅收紧extension_schema_installation的runtime写权，不存在正式License source/head初始化。

| 合同项 | 实际源码/权威 | 当前能证明什么 | 未闭合项 |
|---|---|---|---|
| installation exact | extension_runtime/current_installation_release_evidence.py:_read_exact_in_transaction；bundle_installation→bundle_installation_revision→bundle_composition→load_stored_lock | current/active revision、etag、状态、selected signed release、lock hash | 返回EVIDENCE_ONLY_NO_START，不能授启动/License发行权 |
| License原始Owner | AipProductionContractStore / aip_evidence_bundle_revision / aip_evidence_bundle_revoke_event | canonical frozen EvidenceBundle及撤销来源；build/create/revoke Receipt | 原build的license_summary语义与独立可信发行政策未闭合 |
| Owner含义 | 原权威服务/原数据库事实，与principal.subject/created_by区分 | 不需要凭空新建“Owner表” | b78提出Owner授权ref仍是未决概念，必须对原authority事实与issuer授权逐项绑定，不能把created_by当授权 |
| production evaluator | aip_capability_binding_service.py:evaluate205–300；routers/aip_bindings.py:build_capability_binding_service/evaluate_capability_binding | 普通路径readiness先计算、后写事务；私有配置用reader和capability_lifecycle issuer | 私有issuer明确AipBindingEvaluatorRequired；尚非b77受限SQL的生产承载 |
| issuer权限 | aip_registry_issuer_connection.py:_ISSUER_LOGINS/_LIFECYCLE_UPDATE_COLUMNS | agent/skill/capability/capability_lifecycle，独立身份与最小列检查 | 没有evaluator command family，不能扩大capability_lifecycle角色绕过阻断 |
| private路由门 | routers/aip_bindings.py:_require_private_capability_write149–156 | REQUIRE_PRIVATE打开且未配置则503；配置reader/issuer同库不同私有passfile | 未核当前环境，不宣称线上503/可写；未读取任何私有认证 |
| policy/八依赖Owner | aip_binding_readiness_service.py:PostgresBindingDependencyAuthority与AipModelRuntimeStore/Resolver | 每类原source/ref/hash等合同入口；license/eval/dataset/route等不同authority | 多来源同事务重算、mutation共同head、缺省可信读取与期限边界还待整体实现 |
| restricted算法 | tests/extension_runtime/plan_restricted_evaluate_case.py | b77真实SERIALIZABLE/trigger/lock/Receipt组合证据 | 随机SQL/helper是test-only，不能复制为生产evaluator或冒称正式API已经存在 |

## 对b78设计的修正

a0v_136作为下一migration候选（具体revision名字长度/唯一性与down_revision=a0v_135须实现前实核）；不是直接修改旧135。普通Evidence源保持兼容；可信发行不能仅靠manifest已签名或nonempty license_summary。安装release reader不可自升权，Registry lifecycle身份不可被拿来当eval issuer，BI独立身份不可跨domain借用。

新正式evaluator落点应是独立命令服务/身份合同，接入既有capability evaluate路由的显式正式配置，默认仍fail-closed；保留普通preview reader和旧family最小权限。不是在现evaluate前挂一段preview然后称共同事务。明确计划文件：新aip_binding_evaluator_service.py与aip_binding_evaluator_connection.py（设计候选），原aip_bindings.py只接线，原readiness resolver增加同事务source读取接口或独立事务authority实现，所有八依赖必须支持当前事务；新License source authority/迁移只是其一个共同依赖。

b78已列source_issuance/head候选表仍不能因“head存在”获得权威；完整source初始化需求缺真实验证过的发行授权事实/政策语义，缺时拒绝，不自动生成旧行head、不改generic source的lifecycle或Receipt。当前库不迁移。

## 下一b80明确实施顺序

先正式八依赖evaluator/source initializer整体方案（文件、DTO、issuer identity、同事务读取、锁序、Receipt、兼容）和独立复核；使用当前可检查源码，与BIND-1 §5一致。先新增不可用正式evaluator的真实HTTP/PG RED和独立身份ACL准入测试，再最小实现source/head schema与同事务命令；不把普通lifecycle身份放宽为eval。License issuer许可来源的未决项继续fail-closed，读者缺源不授权；独立W-L20来源路径可继续。不得把增加空服务/永远503占位当成最终实现或完成证据。

本wave仅静态mapping与Alembic头实读，未做业务副作用或运行验证，不声称正式安装、配置或首链完成。Goal active；current135只读/Host等独立授权门不变。

路径更正：首版migration描述名误写，实际rg和source-hashes均指向a0v_135_extension_schema_acl.py；仅更正文档，唯一head135结论不变。
