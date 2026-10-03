# E17-s3o-w-ao-b26｜Capability operation 发行证明文件级方案

## 上位与当前事实

- 231-4 要求共享 PostgreSQL 单一权威、显式表/列命令白名单、非 owner 专用角色、FORCE RLS、固定 search_path、全局串行迁移；BIND-1 §6.1 要求租户隔离、CAS/幂等、Receipt 与真实运行绑定。b25 新一致备份完整恢复到无网络 test-only 新库，源/克隆 604 关系、14,496 有效权限、590 RLS 策略摘要相同；原库仍 `a0v_135` 只读，当前 Capability 写503。
- b24 test-only 标记把未变 status/health 的任意 UPDATE 归为 evaluate。b25 克隆回滚事务证仅 version+updated_at 的写入可配伪 evaluate Receipt，且 readiness 仍 unknown/评估时间 NULL。现有正式 issuer 工厂 `aip_registry_issuer_connection.py` 同时要求普通 runtime 对共享 Receipt INSERT=false；当前 runtime 为 true，普通 Agent/Skill/Run/Handoff 也使用该表，不能全表撤权限。

## 改动目标与文件

1. 先在 `services/aos-api/tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py` 的既有完整迁移 disposable DB test-only 守卫加入最窄 RED：issuer 以 version+updated_at 假更新配 evaluate Receipt 必须拒绝，合法 evaluate 的 readiness快照仍正向。另加混合 status+评估快照、同事务多 Receipt、普通共享 operation 兼容负/正例；先观察明确失败后只修 test-only 判定，不接当前原库。
2. test-only 数据库派生 operation 形状候选：create=INSERT version1/provisioning；update=status 必变化且 observed_at 与版本 CAS 保持一致、不得改变评估快照；evaluate=status/health 不变，last_evaluated_at 必从旧值递增，dependency_snapshot_hash 非空、readiness_expires_at 晚于 last_evaluated_at，且不能修改状态字段。三类只允许一次行写对应同租户/同版本/同事务 Receipt；普通 operation 不受影响。没有满足形状的 UPDATE 直接拒绝，不能默认分类为 evaluate。
3. 原生产候选文件为 `services/aos-api/alembic/versions/a0v_136_*.py` 和 `services/aos-api/aos_api/aip_registry_issuer_connection.py`；先验证历史 Binding 行的缺省/迁移兼容、触发器禁用权限和正式独立 issuer 登录，再决定是否新增迁移。当前源库无 Binding 行不代表其他环境无历史行。生产 issuer 必须非 owner、不能借 `SET ROLE` 或可写 session GUC。普通 runtime 对共享 Receipt 仍保留合法 INSERT，但 Capability operation 必须被精确拒绝。更新工厂预检前要有实际 operation scoped DB 守卫验证，不能只放宽布尔位。
4. 按 RED→最小隔离实现→专项/相邻回归→方案/代码复审→verification→m1精确提交收口；涉及正式迁移时再执行新独立备份、ACL/数据全恢复、迁移/降级有界演练、零执行窗口。当前真实库只读、Host/worker/Provider关，org-org/dev-project唯一正向，dev-org零副作用，不读商城源/不回放旧12Run/不手工run_definition/不碰230 L0/不push。

本波若 RED 证明候选形状仍能伪造，先更新方案再做更小的受控命令入口，不把测试 GREEN 等同正式身份或自然首链。
