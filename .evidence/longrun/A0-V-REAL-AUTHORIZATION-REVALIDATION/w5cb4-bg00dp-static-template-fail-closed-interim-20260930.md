# W5CB4 BG00dp｜BI 本地静态模板生产捷径禁入（中间检查点）

| 验证 | 命令/边界 | 退出码与结果 |
| --- | --- | --- |
| RED | `uv run --project services/aos-api pytest -q services/aos-api/tests/aip/test_aip_responsibility_template_authority.py -k local_bi_template_hash` | 1；实际 `resolve_responsibility_template` 对本地静态 BI ref 返回 true，预期 false。 |
| 禁入及相邻单测 | `uv run --project services/aos-api pytest -q services/aos-api/tests/aip/test_aip_responsibility_template_authority.py services/aos-api/tests/test_ecommerce_business_investigation_aip_authority.py services/aos-api/tests/test_ecommerce_analysis_compilation_roles.py services/aos-api/tests/test_ecommerce_business_investigation_aip_readiness.py --disable-warnings` | 0；56 passed。旧角色读取单测将签名来源检查隔离为测试替身，仅保留角色读取行为覆盖，不视为业务验收。 |
| 相邻 PG 用例 | `uv run --project services/aos-api pytest -q services/aos-api/tests/extension_runtime/test_analysis_context_preparation_pg.py -x --disable-warnings --tb=short` | 1；fixture 在发布 Skill 的 `derive_gate` 报 `formal Skill Eval executor authority unavailable`，未进入本次修改逻辑；正式 Eval 来源仍需独立解决。 |
| 代码检查 | `git diff --check` | 0。 |

生产解析器不再以本地静态 hash 证明签名模板；materializer 先只读检查模板来源，未通过则在 Stage/Plan 写入前拒绝。当前代码仍用历史 `build_responsibility_plan_request` 静态 ref，因此此切片**只有禁入，没有 approved 安装的正向配置准备**。后续必须从真实签名 artifact/唯一批准安装/精确 lock 形成 ref，并复核 `ecommerce_analysis_compilation_roles.py` 的 `domain.responsibility_template_code == template.resource_id` 静态 ID 假设；不能通过模拟测试或放宽 active 解析器冒充首链。当前真库未用于这些命令，Host/worker/Provider 仍关；BG00dp 任务继续 ACTIVE。
