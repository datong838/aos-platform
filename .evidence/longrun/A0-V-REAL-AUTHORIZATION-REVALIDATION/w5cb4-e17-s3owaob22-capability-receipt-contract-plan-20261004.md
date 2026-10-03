# E17-s3o-w-ao-b22｜Capability 共享 Receipt 精确发行合同文件级方案

## 已读上位与当前事实

- 231-4/BIND-1 要求 tenant scoped、expected-version CAS、幂等 Receipt、独立 issuer；b19 已在忠实 ACL克隆证明 owner `SET ROLE aos_runtime` 可插入无 Binding 的 `capability_binding.create` Receipt，但独立非owner runtime登录在当前 DB CONNECT处关闭。b20 当前签名预览写503，b21只证明同一无网络克隆 Reader私有登录与RLS，不涉及 issuer放行。
- b12 Tool在一次性全迁移 test DB 中用真实非owner登录、INVOKER Receipt触发器与 deferred Binding反查测试过双向配对；其 `xmin` 仅是隔离探针。Capability 原 `RegistryReceipt.result_ref.revision=None`，不可把 Tool探针直接复制成生产迁移；共享 Receipt还有 Agent/Skill/Run等合法 operation，不能全表撤 runtime INSERT。

## 文件级施工次序

1. 只读列出 Capability create/update/evaluate 的真实 Store写序、Receipt operation/resource_ref/result_ref形状、当前共享 Receipt合法 operation集合；对照 b12 Tool测试与 b19克隆 ACL/DB CONNECT。先确定可持久的 Binding版本来源与同事务配对规则，凡需要公共 DTO/迁移裁决的点写成明确待决事项，不擅自批准。
2. 在独立一次性 test DB 或 b17忠实 ACL克隆（选一个不影响 b21 Reader证据的路径）写 RED：真实独立 runtime登录插无配对 Capability Receipt 若能成功，记录原缺口；issuer/普通 operation正反例都必须有。仅 test-only建真实专用issuer身份与最小 ACL，不用 owner `SET ROLE`冒充发行者。
3. 若合同充分，再以最小 test-only DB守卫验证：Capability operation仅精确发行者、同租户、当前 Binding版本、同事务相互配对；runtime普通 Agent/Skill等 operation继续通行。测试无配对/错版本/跨租户/旧行补Receipt/重复/回滚和正向。若当前 `revision=None`无法安全配对，就停在协议 RED与证据，不改正式 Store/迁移，转当前八配置/六Binding独立来源代码项。
4. 专项与相邻回归、方案/代码一致性复审、verification、m1精确提交，01/06/D-waves/Prime同步。仅 test DB变动不重启生产 API/Web；生产代码若后续改变，按原卷最新 m1重新完整重启并浏览器复验。

边界：当前原库只读、Host/worker/Provider关、`org-org/dev-project`唯一正向、`dev-org`零副作用；不读商城源、不回放旧12 Run、不手工 Run、不碰230 L0、不 push。
