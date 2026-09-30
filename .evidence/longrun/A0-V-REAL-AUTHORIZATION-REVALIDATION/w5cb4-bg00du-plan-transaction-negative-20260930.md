# W5CB4 BG00du｜BI Plan 事务负向与回滚文件级方案

## 上位与当前

复习 231/231-3/231-9、BG00dr/ds/dt。BG00ds 新入口只创建 draft Plan，当前真库只读；BG00dt 证实当前无 growth1.12、克隆六实例全为 provisioning，不能以伪造 OIDC 或开发 actor 跑正向。负向代码验证只在 isolated test PG 执行，不作为正式业务验收。

## 最小施工

1. 先在 `services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py` 与必要的 `tests/extension_runtime/` 增 RED：dev/错租户认证在 DB 前拒绝；安装非 approved、签名选择不一致、六实例非 active 在 Receipt 前拒绝；当前 permission 拒绝后签名解析器不被调用；Plan 插入后模拟 Receipt 失败则同事务回滚。异 body/actor/安装 ETag 复用 key 必须由 `AipProductionContractStore._replay` 拒绝。
2. 核对 `aip_production_contract_store.py` 的 in-transaction API 是否对非事务/异 operation 请求开放越界；有缺口才最小收紧，不改旧 `responsibility_plan.create` hash。测试要使用独立 PG 或单元替身，清楚区分可验证的事务原语与未具备的正式身份链。
3. 跑专项/相邻回归、编译/diff、只读当前与 clone Receipt 数；适用时浏览器只验阻断，不进行未授权写入。记录效果 0、失败码及未证项。

本波不改当前库、不启 Host/worker/Provider、不读商城源、不写 dev-org 当前实例、不重放旧 12 Run、不手工 run_definition、不碰 230 L0、不 push。
