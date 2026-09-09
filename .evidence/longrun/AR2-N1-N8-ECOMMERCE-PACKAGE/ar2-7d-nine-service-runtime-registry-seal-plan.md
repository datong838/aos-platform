# AR2-7D 九 HostService 生产 Registry 总封板施工卡

日期：2026-09-09
基线：`aos-platform/m1@fe253594`；`docs/m1@58b183a`
状态：专项验证完成，不执行 dispatch cutover

## Rules 与方案复核

- 以 closure manifest 与 231-6 AR2-7D-D1/D4 为权威；m1 单人串行、方案先行、最小改动、证据后精确提交；不 push，230 L0 挂起。
- 九项 HostService 已分别完成真实 authority 回读、领域 Receipt 写入/回读与专项验证；最后一项 Analysis UNKNOWN 只安全进入 RECONCILING，不把未解析 target 冒充成功。
- 本切片只解除 Python 生产 registry 的 5/9 review seal，不修改数据库 dispatch binding，不启用真实租户，不调用 Provider、真实源或外部动作。

## 实现范围

1. 修改 `services/aos-api/aos_api/ecommerce_growth_host_composition.py`：将 `RUNTIME_WIRING_PROVEN_OPERATIONS` 提升为固定九项全集；继续要求 operation order、adapter spec、HostService 三方法和三项平台依赖全部精确成立，否则整组 `AR2_7D_RUNTIME_WIRING_REQUIRED`。
2. 修改 `services/aos-api/tests/extension_runtime/test_ecommerce_growth_runtime_registry.py`：以实际 HostService 证明无参数 runtime factory 与 production selector 均为九项 runtime binding；保留缺类、依赖漂移、顺序/集合漂移时整组失败关闭反证，禁止局部启用。
3. 回归 registry、canonical router/HTTP、九 HostService、HostPort、runtime Store 与完整 extension runtime；运行 closure、memory、compile/diff 和独立只读复审。

## 退出条件与后续

- 仅当实际九服务可构造且所有回归通过，记录 `AR2_7D_NINE_SERVICE_RUNTIME_REGISTRY_SEAL_GREEN`。
- 该门只表示生产进程可构造完整 runtime registry；数据库仍由当前 dispatch/fence/generation/epoch 决定是否可派发。下一项进入 D5 整组 cutover 的 prepare/commit/rollback authority，不得把本提交称为业务切换完成。
