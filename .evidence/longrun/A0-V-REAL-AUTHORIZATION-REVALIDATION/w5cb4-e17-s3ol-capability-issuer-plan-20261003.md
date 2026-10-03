# W5CB4 E17-s3o-l｜原 CapabilityBinding create 独立发行计划

日期 2026-10-03。依据 231 总控/231-4/231-9、583 与 D-waves s3ok 下一波。按最小切片先证 create/replay 同事务 Registry Receipt；evaluate/update 的 readiness reader 由另一连接工厂承载，须单独核其真实身份、依赖表权和 CAS，不因 create GREEN 宣称生命周期或 active。

## 原路径与文件

- `services/aos-api/aos_api/aip_capability_binding_service.py:create`：先 SELECT 不可变 `aip_capability_revision` exact published，查同租户已有 `aip_capability_binding`，INSERT provisioning Binding 与 `aip_agent_registry_receipt`，同事务提交；replay 使用 Receipt hash，失败不应留半行。原 Store 不改。
- `services/aos-api/aos_api/aip_registry_issuer_connection.py`：新命令族 `capability` 只接独立 `aos_aip_capability_issuer`，私有 passfile/精确库与租户、非 owner/BYPASSRLS/无 runtime 成员、固定超时。要求 CapabilityRevision SELECT、CapabilityBinding SELECT/INSERT 且 FORCE RLS、Registry Receipt SELECT/INSERT 且 FORCE RLS，普通 runtime 无 Receipt INSERT；拒绝 Agent/Skill/Tool/Assignee 写权、CapabilityBinding UPDATE/DELETE。Agent/Skill 原两身份权限不变；默认不接当前 API/Host。
- `services/aos-api/tests/aip/test_e17_s3ol_capability_issuer_pg.py`：一次性自动销毁 PG135 与 test-only 发布 Capability 夹具；先原 create 缺独立身份的 RED，再验证独立角色原 create/replay、同键异内容、跨租户不可见、普通 runtime 直插拒绝、能力 revision 未发布/无权限/ACL返宽失败关闭。夹具不代表正式签名能力。

只在隔离库建角色/策略；当前真实库只读。验证专项和 s3oi/s3oj/原 Capability 相邻、语法与差异，适用时仅本机 API 局部重载。verification 后 m1 精确提交，AOS/Prime/01/06、D-waves 与接续同步。回滚移除未正式接线的命令族及隔离测试；不改安装、迁移、真实数据。
