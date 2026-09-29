# W5CB4 BG-00q｜正式 Skill Eval Contract 入口禁入验证

方案：`w5cb4-bg00q-formal-skill-eval-admission-plan-20260929.md`；基线 `aos-platform/m1@30dec072`、权威 `AOS-000865`。修改仅 `services/aos-api/aos_api/aip_eval_runner.py` 和 `services/aos-api/tests/aip/test_aip_eval_runner.py`，不加迁移、不写当前业务库。

## RED → GREEN

- 5433 为 `aos-a0v-test-only` 的独立 `aos-a0v-test-pg`；环境无 `AOS_DATABASE_URL`，`db.py` 默认指向 `127.0.0.1:5433/aos_meta`。新增测试在独立随机 schema 建表，测试后删除该 schema。RED 命令：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_runner.py::test_formal_skill_contract_rejects_unattested_callbacks_before_run`，退出 1，`Failed: DID NOT RAISE AipEvalAuthorityConflict`。这复现了正式 exact Skill Contract 可由注入回调生成 Eval 结果的缺口；仅为隔离测试证据，不是业务执行。
- GREEN：`run_by_contract` 在调用 `run()` 前，同租户读 Contract 的 exact Suite，核 Suite ref hash 与 Suite canonical hash；Skill target 因尚无独立 Judge/Target executor authority 而抛 `AipEvalAuthorityConflict("formal Skill Eval executor authority unavailable")`。新增测试断言 resolver/target/judge 回调调用数 0，隔离 EvalRun/Report/Gate 数 0。另有 Suite hash 漂移前置拒绝测试。
- 专项+相邻累计命令：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_runner.py services/aos-api/tests/aip/test_aip_eval_pack_registry.py services/aos-api/tests/aip/test_aip_release_publication_service.py services/aos-api/tests/aip/test_aip_skill_publication_service.py`，退出 0、`29 passed`。`python -m compileall -q` 针对两文件退出 0，`git diff --check` 退出 0。
- 当前库容器内 `BEGIN READ ONLY` 回查 `aos_current_preview_20260927@a0v_111`，栖月汇 EvalRun/Report 仍 `0/0`，退出 0。未触碰 `dev-org` 正向数据、商城源、Host/worker/Provider、旧 12 Run 或 230 L0。
- 提交 `m1@b0d245cc` 后，原 API session `74149` 收到 Ctrl-C 并退出 0，8080 监听消失；新 session `89019` 以相同正式签名 Receipt 和新代码 `--serve` 启动。8080 `/v1/health`、`/v1/ready` 与 8434 `/aip/skill-publish` 均 200；18181 保持无监听。未重启 PG/迁移/Web，此为今日 09:04 完整重启后的代码重载。

## 方案一致性与残余风险

本波实现了方案的正式 `run_by_contract` 负向门，原 Logic Contract 正例保持，旧 `run()` 与 Skill 发布隔离测试保持既有语义。这个范围**没有封死直接 `run()` → Report → E2 Gate/Publication 路径**；现有 Skill 发布测试正使用该路径和注入 lambda，因此仍是 BG-00r 必须处理的正式发布风险，不能将本波称为全部 Eval/发布权威完成。下一波须先定义可独立核验的 Judge/Target 签发与执行 Receipt，随后在 E2 同事务发布门关闭未证明来源；不能以测试开关或回调自报放行。当前 G2 正式内容格式/签发 Owner 和 BG-00o 真实 S3 读回仍缺。无页面逻辑改动，HTTP 200 不提升八工作台或首链验收等级。
