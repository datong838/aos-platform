# E17-s3o-w-ao-b23｜Capability Receipt 持久版本与共享表兼容方案

## 上位方案和当前事实

- 231-4 要求共享 PostgreSQL 显式表所有权、租户 RLS、审计与业务 runtime 分离；BIND-1 31 要求 CapabilityBinding tenant scoped、expected-version CAS、幂等 Receipt。b22 `m1@ca7ec63a` 只在一次性完整迁移 test DB 证明独立 issuer/同事务配对，保留原缺口 strict xfail。
- 原 `AipCapabilityBindingService.create/update/evaluate` 分别写 Binding 版本 `1`/`version+1`/`version+1`，随后同事务 `_insert_receipt`；结果类型依次为 `CapabilityBinding`、`CapabilityBinding`、`CapabilityBindingReadiness`。共享 `AipAgentRegistryStore._ref()` 把所有 `ResourceRef.revision` 固定为 `None`，因此 b22 test-only 显式版本正向并非原 Store 正向。AgentInstance create/update 也复用 `_insert_receipt`；其他 Store 操作和迁移中合法 operation 需逐项列全，不能凭两条示例给全表改 ACL。

## 文件级施工顺序

1. 只读列出共享 Receipt 表所有直接/间接写者、operation、result_ref 形状、幂等唯一约束与既有行为测试；核对当前签名预览五类 Capability 写503及正式发行身份缺口。记录最小兼容矩阵，尤其旧 Receipt `revision=null` 回读与当前幂等重放。
2. 在 `services/aos-api/tests/aip/` 一次性完整迁移 test DB 对**原 Store**写 RED：create/update/evaluate 的返回 Receipt 结果版本须等于已落库 Binding 版本；无版本或非独立 issuer仍被正式 DB 门拒绝。不能依赖手工造行或把 b22 test-only `xmin` 当持久契约。若原 Store 需要正式来源才能完整驱动，先拆纯版本 DTO/SQL RED 与隔离 issuer 门，不伪造正式签名来源。
3. 若兼容矩阵与持久配对规则充分，先在本文件追加逐项 SQL/身份/回滚协议，再最小改 `_insert_receipt` 的可选结果版本与三处 Capability 调用，保持 Agent/Skill/Run 原回执不漂移。正式 ACL/迁移仅在独立全备、完整恢复、合法私有发行身份、零执行窗口另波执行；本波不得写当前真实库。
4. 专项/相邻回归与旧 Receipt 回读、方案/代码复审、verification；如改生产代码则按当前权威卷最新 m1 严格 PG→API→Web 重启并浏览器验收。收口精确 m1 提交、01/06/D-waves/Prime 同步并进入下一波。

边界：`org-org/dev-project` 唯一正向、`dev-org` 零副作用；当前库只读，Host/worker/Provider关；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。外部身份或公共协议局部待裁决时继续八候选/六 Binding 独立主线，不置整个 Goal blocked。
