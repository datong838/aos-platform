# W5CB4 BG00dq｜active 签名 BI 职责读取中间检查点

| 检查 | 命令/来源 | 退出码与结果 |
| --- | --- | --- |
| RED | `uv run --project services/aos-api pytest -q ...test_active_bi_business_reader_is_separate_from_approved_preparation ...test_ecommerce_analysis_compilation_roles.py` | 1；2 failed：缺 `ActiveBIBusinessResolver`、业务读取端将签名 artifact URI 与静态 domain code 比较。 |
| 最小实现 | `aip_responsibility_template_authority.py` 的独立 active BI 读取复用 BG00dp 签名/lock/artifact 校验，只查询 `active_revision=current_revision`、state active；`ecommerce_analysis_compilation_roles.py` 用签名 payload 的 `templateId` 对齐 domain code，并核对当前 Owner 安装 ID | 未放宽旧内容 `_row_matches` 或 approved 准备态；当前状态无业务许可。 |
| 专项相邻 | `uv run --project services/aos-api pytest -q services/aos-api/tests/aip/test_aip_responsibility_template_authority.py services/aos-api/tests/test_ecommerce_analysis_compilation_roles.py services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py services/aos-api/tests/test_ecommerce_business_investigation_aip_readiness.py --disable-warnings` | 0；65 passed。单测使用替身隔离模板来源，只证明角色读取逻辑与负向检查，不计真实 active 验收。 |
| BG00dm 克隆只读 | 克隆 DB URL、签名根/信任根/alias 环境下，`ApprovedBIPreparationResolver.select(org-org/dev-project)` 与 `ActiveBIBusinessResolver.load(scope, exactRef, installation_id)` | 0；approved 准备态有签名模板；active 读取返回 None，active 安装行0；dev-org 返回 None。无状态修改。 |
| Owner 边界复核 | `pipeline_source_selection_owner.py:160-255` | 已核到 `run_current_snapshot` 在当前事务对安装 `FOR UPDATE`，检查 active baseline、binding/config 与当前签名 release；本波模板检查仍重读来源，未取代 Owner/broker 准入。 |

仍无合法 active1.12 安装，因此没有 active 正向验收。要做正向需另建可恢复 test-only 全生命周期演练，不能直接 UPDATE 指针或将 approved 当 active；当前真库只读，Host/worker/Provider 关闭，首链 pending。BG00dq 任务继续 ACTIVE。

## 同波只读复核：合法 active 正向入口

2026-09-30 17:20 CST，读取 `bundle_runtime_installations.py:127-147,340-347`、`lifecycle_service.py:46-105`、`runtime_host.py:131-146`、`control_wiring.py:115-230` 和 `scripts/a0v_current_runtime_host_preflight.py:66-166`：`runtime-apply/verify` 的接受条件包含进程内 ACTIVE Host、当前精确租户 assignment，以及签名安装/三类独立数据库身份/Host assignment 预检。`runtime-verify` 还要求该安装已有 lifecycle Owner。不能用 `InstallationService.apply/verify` 或直接改 `active_revision` 绕过这些条件。

| 只读命令 | 退出码与结果 |
| --- | --- |
| `services/aos-api/.venv/bin/python scripts/a0v_growth_112_formal_source_audit.py --current-signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json --successor-signed-receipt /Users/ddt/work/projects/ai_agent/.aos-growth-112-signing-receipt-r3-20260930.json` | 0；两库 a0v_118，Host identity/assignment/operation/binding/config 与八候选全 0；当前无 growth1.12、克隆有已签名 growth1.12；`formalReady=false`、`effects=0`。 |
| `services/aos-api/.venv/bin/python scripts/a0v_current_runtime_host_preflight.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json --preparation-only` | 2；`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。无 Host 启动、无数据库写。 |

结论只限本次受检正式入口：当前无法合法启动 Host 走完整 active 状态机，test-only 的签名 clone 也缺三身份和 assignment。该实例正向验收继续 pending；不伪造授权、不用测试替身计作验收。接着做不依赖 Host 的代码与契约检查，用户长期 Goal 不改状态。
