# AR2-7D 九 HostService 生产 Registry 总封板验证

日期：2026-09-09
基线：`aos-platform/m1@fe253594`；`docs/m1@58b183a`
结论：`AR2_7D_NINE_SERVICE_RUNTIME_REGISTRY_SEAL_GREEN`

## Rules 与结果

- closure manifest 与 231-6 D1/D4 为权威；m1 单人串行、最小变更、无 push；230 L0 挂起。
- `RUNTIME_WIRING_PROVEN_OPERATIONS` 从已验证的前五项提升为固定九项全集；无参数 runtime factory 和 production selector 均构造九项实际 HostService。
- 构造前仍核对平台依赖、operation 全集/顺序、adapter spec 和三方法；任一缺类、依赖或顺序漂移，runtime factory 整组拒绝，selector 的九项全部回退 registration-only，不产生局部启用。
- 本切片没有读写 dispatch/fence/generation/epoch，不构成数据库 cutover。

## 验证

- registry 专项：`7 passed`，覆盖实际九服务、production selector、无注入面、缺类整组回退、依赖与顺序漂移拒绝、HTTP 只选择 production selector。
- 九服务、Canonical Router/HTTP、HostPort 及 Content/Review/Analysis 邻接：`226 passed`。
- 完整 `tests/extension_runtime`：`741 passed, 471 skipped`。
- Python compile、`git diff --check`：通过。
- Closure：`1707 scanned / 91 classified / 57 migrated`；五类错误集合为空。
- Memory validate：`AOS-000571 / GREEN / 865 Delivery Receipts / 2226 events / 846 Task Receipts`。
- 独立只读复审：无 blocker/major；补充的 selector 缺类回退反证已通过。

## 无效环境运行与边界

- 首次邻接命令包含两个不存在的旧测试文件名，pytest 未执行用例；按当前真实文件枚举后 226 项通过。
- 旧 `test_ecommerce_growth_host_ports_pg.py` 自身固定连接 18432，系统重启后该端口未启动，产生 3 个连接错误；该历史专项未因本切片修改。本轮不启动第二数据库，既有 HostPort/各 HostService 组合证据与标准套件继续有效。
- ContentGenerate 仍只产生确定性 `FAILED_NO_EFFECT`；Analysis UNKNOWN 仍只进入 RECONCILING。九服务可构造不代表完整业务成功链、真实 Provider 或真实租户 dispatch 已启用。
- 下一项是 D5 整组 cutover authority 与 9/9→0/9 回滚验收；真实源、Provider、生产迁移、外部发布与 230 L0 均保持关闭。

## SHA-256

- `ecommerce_growth_host_composition.py`：`9b554a75b6a598ab4252eba3750c5228e44efc6df6aef64c203216d7786f4878`
- `test_ecommerce_growth_runtime_registry.py`：`ad6d1db830fe1299be83af9b662085f222b01f8ec15f93c9e398248c61357a5a`
