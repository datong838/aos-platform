# W5CB4 E17-s3o-w｜职责 Plan 只读稳定版本与独立发行方案

日期：2026-10-03。复习 231-3/5/9、栖月汇全店经营执行方案、原 `AipProductionContractStore` create/revise/freeze 和 `read_current_responsibility_plan_ref`。上一波隔离 RED 证明：`aos_runtime` 的职责 Plan 写权收窄后，原 `FOR SHARE OF h` 读取消费报权限不足；保留写权则普通 Host 可伪造 current Plan/Receipt，不能拿一个方向的 GREEN 冒充另一方向。

## 文件级顺序

1. 在 `services/aos-api/tests/extension_runtime/` 增加真实 PG 最小试验：普通无 owner/无写权会话分别尝试原行锁读、候选表锁、纯 SELECT；记录实际权限与锁模式，不用 mock。若表锁需要写权或有跨租户互堵风险，拒绝该路径。
2. 复查 `aip_production_contract_store.py` 所有 Plan head/Receipt 原写入口及 DB migration/grant/RLS；列独立 issuer 必要登录、最窄表权、Receipt 同事务与相同键重放、跨租户和 runtime 直写拒绝，先定义测试 RED。不得以 `aos_app` owner/超级用户作为正式 issuer。
3. 若存在不增加 runtime 写权、能与全部合法 Plan 发布者协同的短事务稳定版本协议，先写方案与 RED，再最小修改原读者/发行路径，跑专项及相邻回归；若协议仍缺口，先收束只读审计证据，不擅自移除行锁或给 runtime 写权。
4. 当前真库只读。任何迁移/正式 ACL 切换另波需新全备可恢复、克隆全链演练、零执行窗口；正式 OIDC/凭据、签名来源和 Host Owner 仍是实例门。浏览器不用于本波底层锁契约。

预期交付：明确可验证的只读稳定版本/独立发行合同，或证据化地排除不安全候选并转已登记 ToolBinding/RETURN 独立项。Goal 保持 active，m1 精确提交、不 push。
