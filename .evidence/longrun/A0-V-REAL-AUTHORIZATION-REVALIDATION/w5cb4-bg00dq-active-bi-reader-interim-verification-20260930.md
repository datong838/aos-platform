# W5CB4 BG00dq｜active 签名 BI 职责读取中间检查点

| 检查 | 命令/来源 | 退出码与结果 |
| --- | --- | --- |
| RED | `uv run --project services/aos-api pytest -q ...test_active_bi_business_reader_is_separate_from_approved_preparation ...test_ecommerce_analysis_compilation_roles.py` | 1；2 failed：缺 `ActiveBIBusinessResolver`、业务读取端将签名 artifact URI 与静态 domain code 比较。 |
| 最小实现 | `aip_responsibility_template_authority.py` 的独立 active BI 读取复用 BG00dp 签名/lock/artifact 校验，只查询 `active_revision=current_revision`、state active；`ecommerce_analysis_compilation_roles.py` 用签名 payload 的 `templateId` 对齐 domain code，并核对当前 Owner 安装 ID | 未放宽旧内容 `_row_matches` 或 approved 准备态；当前状态无业务许可。 |
| 专项相邻 | `uv run --project services/aos-api pytest -q services/aos-api/tests/aip/test_aip_responsibility_template_authority.py services/aos-api/tests/test_ecommerce_analysis_compilation_roles.py services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py services/aos-api/tests/test_ecommerce_business_investigation_aip_readiness.py --disable-warnings` | 0；65 passed。单测使用替身隔离模板来源，只证明角色读取逻辑与负向检查，不计真实 active 验收。 |
| BG00dm 克隆只读 | 克隆 DB URL、签名根/信任根/alias 环境下，`ApprovedBIPreparationResolver.select(org-org/dev-project)` 与 `ActiveBIBusinessResolver.load(scope, exactRef, installation_id)` | 0；approved 准备态有签名模板；active 读取返回 None，active 安装行0；dev-org 返回 None。无状态修改。 |
| Owner 边界复核 | `pipeline_source_selection_owner.py:160-255` | 已核到 `run_current_snapshot` 在当前事务对安装 `FOR UPDATE`，检查 active baseline、binding/config 与当前签名 release；本波模板检查仍重读来源，未取代 Owner/broker 准入。 |

仍无合法 active1.12 安装，因此没有 active 正向验收。要做正向需另建可恢复 test-only 全生命周期演练，不能直接 UPDATE 指针或将 approved 当 active；当前真库只读，Host/worker/Provider 关闭，首链 pending。BG00dq 任务继续 ACTIVE。
