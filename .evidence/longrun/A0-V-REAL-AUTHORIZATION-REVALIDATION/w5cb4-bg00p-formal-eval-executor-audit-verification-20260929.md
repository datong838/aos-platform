# W5CB4 BG-00p｜正式 Eval 执行身份只读审计

方案：`w5cb4-bg00p-formal-eval-executor-audit-plan-20260929.md`。基线 `aos-platform/m1@f9e8b61d`、权威 `AOS-000864`。本波没有修改业务代码、迁移、测试或当前库。

## 今日重启后再核

| 读回 | 命令与结果 |
| --- | --- |
| 分支与工作树 | `git branch --show-current`=`m1`；`git rev-parse --short HEAD`=`f9e8b61d`；已有浏览器插件、`pnpm-lock.yaml` 和两个 `w5c8i` test-only 文件的差异保持不动。 |
| 当前卷和迁移 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg --format '{{range .Mounts}}{{.Name}} {{.Destination}}{{end}}'`=`aos-a0v-recovery-pg-data /var/lib/postgresql/data`；容器内 `BEGIN READ ONLY; SELECT version_num FROM alembic_version; ROLLBACK;`=`a0v_111`，代码头 `a0v_111_budget_active_insert_gate.py`，均退出 0。 |
| 今日备份 | `shasum -a 256 .aos-daily-backup-20260929-oXxcWz/aos_current_preview_20260927_a0v111.dump`=`e527a55cbe5fca5b32754ac08257d3d1908a895ac16b68103794d3830e868b3d`；`docker ... exec -i ... pg_restore --list < dump | wc -l`=`5551`，退出 0。未做全库恢复演练。 |
| 签名/安装来源 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 退出 0，返回 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、当前库 `aos_current_preview_20260927@a0v_111`、approved 安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813`、四个 published bundle、runtimeBindings=0。 |
| 服务 | `curl` 对 8080 `/v1/health`、`/v1/ready` 及 8434 `/aip/skill-publish` 均 200；18435/5433/8080/8434 监听，18181 未监听。今日 09:04 完整 PG/API/Web 重启原证据见 `w5cb4-daily-latest-stack-20260929-0904.md`；这次只是读回，不把 HTTP 200 称为业务验收。 |

## Judge/Target 权威缺口

1. `aip_eval_contracts.py` 的 `JudgeRevisionRef` 只有 `judge_id/revision/content_hash/model_route` 字段；`EvalSuiteRevision` 引用 target/dataset/judge exact refs。`aip4_001`～`003` 迁移保存 `judge_ref`/`target_ref` JSONB，但没有 Judge 版本身份、签发/撤销或执行器证明表。当前库 `pg_tables` 对 `aip_eval%`、`%judge%`、`%executor%` 的只读目录返回 Eval Contract/Dataset/Suite/Run/Report 表，无 Judge/Target executor authority 表，命令退出 0。
2. `AipEvalRunner.run_by_contract` 虽先核 frozen/ready EvalContract，仍由调用者传 `resolve_artifact/execute_target/execute_judge`。`run` 在执行这些回调前创建 QUEUED/RUNNING；只核回调返回的 target/judge ref 等于 Suite ref，未证明回调的进程身份、签名制品、撤销状态或真实执行 Receipt。见 `aip_eval_runner.py:95-128,144-254`。因此 exact ref 和结果哈希不能充作正式执行来源。
3. `_assert_target_not_withdrawn` 按同租户 `aip_publication_event` 排除 revoked/suspended/deprecated，是已有负向保护；它不核目标执行器身份，也没有 Judge 的同类撤销读回。`AipReleasePublicationService` 核 Run succeeded、Report/Suite/target/dataset/judge exact refs 与 Skill evaluated 状态，但若上游是注入回调形成的 Report，这些检查不独立证明执行来源。见 `aip_eval_runner.py:375-398`、`aip_release_publication_service.py:390-449`。
4. `rg -n 'run_by_contract\(|AipEvalRunner\(' services/aos-api/aos_api` 只见 Runner、本身的 `BusinessInvestigationEvalCoordinator` 和 Report 只读消费者；路由没有正式 Eval Run POST。当前库 `BEGIN READ ONLY` 的 `org-org/dev-project` Suite/Run/Report/Gate 计数为 `0/0/0/0`，命令退出 0。不存在可接续的当前 D01 正式 Eval。
5. 既有 `test_aip_skill_publication_service.py` 使用注入 lambda 产生 Skill Eval 报告并走发布门，是隔离测试链，不能当作当前 D01 正式证据。228 G2 的内容事实性/渠道适配与 231 首链的真来源、自然执行仍待实现。

## 下一波最小接线决策

BG-00q 先为“正式 Skill Eval”定义不可由调用方自报的执行权威输入与受理门，保留历史 Logic/隔离测试的原有语义。文件级计划先锁定 `services/aos-api/aos_api/aip_eval_runner.py`、`aip_eval_contracts.py`、`aip_eval_pack_registry.py` 与隔离测试；RED 要证明缺 Judge/Target 当前身份、租户、exact 版本、签名、撤销或执行 Receipt 时，在创建 EvalRun 前失败且 Report/Gate 为零。先审真实可复用身份来源，再决定是否需要新增 authority Store/迁移；若需要，独立克隆波验证后才考虑当前实例迁移。不能以可注入 `callback`、`mock` 或 `dry-run` 作为正向生产身份。

BG-00o 固定 MinIO registry TCP 443 当前再次 `curl -I --max-time 8 https://registry-1.docker.io/v2/` 退出 28，`status=000`；仍无隔离 S3 回环。当前库保持只读；Host/worker/Provider、旧 12 Run、230 L0 与手工 `run_definition` 均未触发。结论是审计完成、正式 Eval/首链未通过。
