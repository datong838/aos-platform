# W5CB4 当前源码新隔离库 Registry 发布子波计划（2026-09-27）

- 上位依赖：`w5cb4-current-code-new-isolated-install-plan-20260927.md` 与 canonical 首装上位方案。`m1@7600e51f` 已独立核实空库 `aos_current_preview_20260927` 到 `a0v_106`，四包持久签名树已通过 ReleasePolicy；仍无 Registry version/Installation。
- 文件级：新增 `scripts/a0v_current_preview_registry_publish.py` 与 `services/aos-api/tests/extension_runtime/test_a0v_current_preview_registry_publish.py`；本计划和 verification 同目录。只用现有 RegistryService/PostgresRegistryStore，不直接 INSERT/UPDATE 模拟发布，不改 ReleasePolicy。
- 顺序：默认只读 preflight 对签名 Receipt、四包 content hash/ReleasePolicy、新库 Alembic/零既有版本与零安装逐项验证；显式 `--publish` 前写外置一次性 intent；creator 建 bundle/version、独立 validator、publisher 依正式 Service 串行推进；每包和最终快照独立读回。未知部分结果不得重发，按 Store/intent 只读对账。
- 测试：错库/版本/Receipt/签名树、已有 state、已有未知 Registry version 均拒绝且零写；成功精确四包、零 Installation/Provider/外部效果。专项与相邻回归、verification、m1 提交后进入 Composition/Installation 子波。
- 不触原 `aos_meta_head`、8080、自然 Host、商城源、旧 12 Run、230 L0 或负向租户写入；`dev-org` 只作零 canary。
