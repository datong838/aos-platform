# W5CB4 BG00EG｜其余七类配置候选核查方案

基线 m1@17d7eed1 / AOS-000994。复习 231 总控、231-1、231-3、BG00EF 清单及当前 01/06。范围限候选统计与正式消费语义，当前数据库不查询或写入。

1. 读 `services/aos-api/aos_api/extension_runtime/runtime_configuration_candidates.py` 与 `configuration_source_catalog.py`，逐类对照当前 head、生命周期、有效期和租户条件。
2. 读 `aip_runtime_configuration_sources.py`、`aip_runtime_configuration_authority.py`、`aip_budget_contracts.py`，区分候选条件与提交时 exact hash/依赖/权限复验。不能把后者全复制到计数器。
3. 仅在存在符合创建契约的可复现误报时补 RED 与最小实现；没有则保留实现并形成逐类对照证据，不写镜像 SQL 测试。
4. 收口 verification、D-waves、Delivery、authority 与 Prime 投影并精确提交。下一波回到 BG00EE 网络消费安全设计，先检查现有批准预检的锁与时效；不无限扩展配置审计。

本波仅新增本方案及对应 verification。页面、服务、当前数据库、角色、Host/worker/Provider 不变；不 push，不读商城源，不重放旧 Run，不手工 run_definition，230 L0 挂起。
