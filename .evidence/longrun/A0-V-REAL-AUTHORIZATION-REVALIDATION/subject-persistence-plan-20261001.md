# Subject 证明持久化第一波文件级方案

用户已批准subject-review设计/实现/隔离验证；基线m1 a100325c/AOS-001075。Rules：AGENTS、aos-engineering-delivery，m1单写、方案先行、RED、最小迁移。当前真实库a0v118只读；新迁移131仅随标准测试建在临时数据库，绝不切当前库。

上位231/GW-b要求双身份真实证明、独立用途、同租户/精确Run/产物绑定；原a0v112 issuer purpose强制eval-execution、identity purpose target/judge，原receipt是Skill执行形状。原持久reader和writer均要求旧用途，不能把subject签成v1 Skill证据。

迁移a0v131：原root与identity表只扩大CHECK允许subject-review及source-witness/judge，保留既有行/ACL/RLS/FK；新增aip_eval_subject_receipt默认空，主键、exact run-case-envelope-purpose唯一性，FK指向EvalRun及原identity证书，Judge sourceClaimHash同租户/同Run/同Case/同envelope外键。严格字段shape、append-only、FORCE RLS；aos_runtime仅SELECT，PUBLIC零权限；无自动身份创建、无高权捷径、无Provider。

测试新test_aip_eval_subject_persistence_pg.py：标准isolated PostgreSQL建库/head迁移，先RED未有131；核head131、原purpose+新用途check、旧表READONLY runtime、subject表无INSERT/UPDATE/DELETE/TRUNCATE、RLS/触发器/FK/唯一索引；runtime tenant可见空表，dev-org与org-org独立；读不到任何当前实例数据。无需构造假issuer/签名当正向业务证据。

仍待后续正式issuer/identity/撤销Owner、持久writer与reader、自然EvalRun事件。新表仅是不可变存储基础，不证明已入库或可授权。若DB字段/约束与原方案冲突则回读修正迁移/方案后再推进。回滚不删除历史证据；downgrade拒绝静默破坏。
