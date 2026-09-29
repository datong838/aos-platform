# W5CB4 BG-00am｜当前正式 Eval 来源与配置候选只读盘点

依据 `w5cb4-bg00am-formal-eval-source-audit-plan-20260929.md`，只读核当前实例；不读取商城源、写当前库、启 Host/worker/Provider 或重发 Run。

| 项 | 当前命令/查询与输出 | 退出码/判定 |
| --- | --- | --- |
| m1 | `git branch --show-current && git rev-parse --short HEAD` → `m1 / 9e4dfe05`；工作树仍有无关浏览器插件、`pnpm-lock.yaml`、两份 w5c8i test-only 文件，均未触碰 | 0 |
| 当前卷/库 | `docker --context colima-aos-extension inspect aos-a0v-recovery-pg` → Running，named volume `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`，127.0.0.1:18435；`SELECT version_num FROM alembic_version` → `a0v_114` | 0 |
| 签名安装 | `scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` → `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`；`aos_current_preview_20260927`、approved 安装1、published bundle4、runtime binding0；`.env` 的 `AOS_BUNDLE_ROOT` 指向存在的当前 signed-bundles | 0；仅签名/安装安全预览 GREEN |
| 正式 Eval | 当前库只读 SQL：`aip_eval_issuer_root`、`aip_eval_executor_identity`、`aip_eval_authority_revocation`、`aip_eval_execution_receipt`、`aip_eval_report_revision`、`aip_eval_case_execution_proof`、`aip_eval_run` 均0行；前六表 RLS/FORCE 均 true；`pg_roles` 中 `aos_aip_eval_writer` 数0。`aos_app` 为 LOGIN/SUPERUSER/BYPASSRLS，不能用作正式 writer | 0；正式双签名/Owner/写身份缺 |
| 三身份/Host | 当前库存在非特权 login `aos_a0v_web_20260912`、`aos_a0v_runtime_20260912`、`aos_a0v_directory_20260912`，但 `.env` 无 runtime/OCI/Eval writer 凭据引用键；当前 Host assignment0、启用 Host identity0。`a0v_current_runtime_host_preflight.py --signed-receipt ...` → `SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED` | 预检退出2；不启 Host |
| 配置候选/租户 | `read_candidates(TenantScope('org-org','dev-project'))` 的 responsibility_plans、runtime_policies、data_policies、egress_policies、network_policies、quota_policies、budget_policies、budgets 八项均0；安装在 org-org/dev-project 1，dev-org/dev-project 0；binding 两租户均0 | 0；仅 dev-org 只读 canary |
| G2 内容/S3 | 当前签名 `solution.ecommerce.growth/1.11.0/content/evals/placeholder.json` SHA256 `e90c23c9234793da6f76f82cc78ceddd677ce47c4c6ed7ced8397bb11d0a69c2`，正文 `BLOCKED / Waiting for G2 review`；`docker image inspect minio/minio:RELEASE.2025-04-22T22-12-26Z` 无镜像，19000 无监听 | image inspect退出1、`lsof`退出1；正式 G2 来源/S3 回环缺 |
| 服务禁入 | API `/v1/health`、`/v1/ready` 和 Web `/aip/skill-publish` HTTP200；18181 监听0 | curl退出0；页面可达不等于首链 |

## 判定与下一波

当前签名制品和安装安全预览可验证，但正式 Eval issuer/Target/Judge/Owner/批准、独立 writer 凭据/ACL、G2 内容/S3、Host assignment/八配置候选均未齐。按 E17 五不得与真实来源要求，当前实例继续失败封闭，不能由 test-only 凭据、历史三身份文件、高权限 `aos_app` 或 placeholder 顶替。BG-00an 先独立审查 BG00ak writer 对正式 G2 签名来源的约束缺口，写文件级方案后只在 test-only 实现必要的来源绑定门；正式 G2 producer/issuer/Owner 仍须合法来源。旧 12 Run、dev-org 写入、230 L0 和手工 Run 均未触碰。
