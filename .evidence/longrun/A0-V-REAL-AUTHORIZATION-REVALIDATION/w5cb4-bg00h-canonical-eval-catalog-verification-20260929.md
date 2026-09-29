# W5CB4 BG-00h 正式 Eval 元数据目录验证（2026-09-29）

## 方案与改动

先读 231 总控、231-1/5/9、栖月汇全店经营产品方案、AIP-4 E1A/B/E2 与 BG-00e，文件级方案见同目录 `w5cb4-bg00h-canonical-eval-catalog-plan-20260929.md`。只在原 AIP-4 Store/Registry 增加租户限定只读目录 API；Dataset 查询仅返回精确 ref 列，不返回 manifest/业务行；Suite 返回既有契约里的 exact refs 与 case ArtifactRef，不执行 Runner。

文件：`aip_eval_authority_store.py`、`routers/aip_eval_authority.py`、两项原测试文件。未修改迁移、发布/运行/Provider/商城数据路径。

## RED/GREEN 与当前实例

- RED：`pytest -q .../test_aip_eval_authority_api.py .../test_aip_eval_pack_registry.py -x`，退出 1，缺 `get_aip_eval_pack_registry`，对应计划中的正式只读目录未实现。
- GREEN：`pytest -q test_aip_eval_authority_api.py test_aip_eval_pack_registry.py test_aip_eval_runner.py test_aip_release_publication_service.py test_aip_skill_publication_service.py`，退出 0，32 passed；其中 Registry 的跨租户写/读仅在 test-only PostgreSQL 隔离 schema，真实库没有注册 Dataset。
- `python -m compileall -q` 两项实现文件与 `git diff --check` 退出 0。
- 以当前签名 Receipt 启动脚本完整重启 8080 API，日志 `database=aos_current_preview_20260927`、`migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`；`/v1/health`、`/v1/ready`、8434 `/aip/skill-publish` 均 200。
- 当前实例 `Authorization: Bearer dev`、`X-Org-Id: org-org`、`X-Project-Id: dev-project`：GET `/v1/aip/eval-authority/datasets` 与 `/suites` 均 `200 []`；`dev-org/dev-project` Dataset 只读 canary `403 AUTH_TENANT_UNKNOWN`，无写入。

## 复审与边界

目录缺失与现有 Store/Registry 能力相符；只读路由不接受客户端 target/租户写入或执行参数，Storage 异常 503 失败关闭，未认证请求拒绝，测试覆盖。AIP-4 旧 E0B2 三只读路由边界在本方案中只向元数据发现扩展，仍不开放 Gate/Publication/Usage 写入。

D01 正式 Dataset/Suite/Run/Report/Gate/Event 当前仍全缺；新 API 仅能审计候选，不能证明来源、评测、发布或经营首链。下一波应接正式来源、脱敏 Receipt、Case/Judge/Target executor 的来源与正向生产机制，真实库写入须另守独立授权门。
