# GW-b-2b bundle accepted-stage 命令生产，运行禁入

2026-10-02 06:18 CST。`ContentTaskSpec` 以默认旧 `issue-review-v1` 保留四个唯一 `ArtifactRevision`；显式 `accepted-stage-v1` 仅允许一个原 `Artifact`。`AcceptedStageHandoffRequest` 用包内原 `AnalystExactRef`/`EvalStageAttemptRef`、原 `ExactRef` 和中文 TaskSpec 构造与宿主严格 parser 相同的 payload；`build_accepted_stage_handoff_command` 只构造，不调用 port。旧 `ReviewHandoffRequest` 不能误收新来源 Task。

RED：新增纯 producer→宿主 parser 测试初次退出 1，`ContentTaskSpec` 不接受 `source_kind`；补判别后再次退出 1，缺 `AcceptedStageHandoffRequest`；补强类型生产后通过。错类型 `stageArtifactRef` 的负例揭露请求级检查不足，修复后通过。最终五文件相邻回归 `tests/extension_runtime/test_ecommerce_review_handoff_content_runtime.py`、`test_ecommerce_review_advance_host.py`、`test_analyst_stage_handoff_source_pg.py`、`test_ecommerce_review_task_brief_authority_pg.py`、`tests/test_sales_weapon_content_task.py` → 68 passed / 7 warnings，退出码 0；`py_compile` 与精确 `git diff --check` 退出码 0。中途曾从仓库根调用不存在的 `.venv/bin/pytest` 得 exit 127，已改用 `services/aos-api` 的真实 `.venv` 重跑通过。

边界：只构造命令，application 没有发送或解析新来源回执；Host `execute` 继续拒绝。当前 BI↔Stage TaskRun 来源关联、Task/Brief v3、内容生成/评审同源校验及正式身份均待；fixture 不是当前自然首链证据。当前真库只读，Host/worker/Provider 未启用。
