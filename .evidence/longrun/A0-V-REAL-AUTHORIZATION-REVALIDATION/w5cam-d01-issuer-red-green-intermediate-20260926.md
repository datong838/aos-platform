# W5cam｜D01 正式 Owner 入口 RED→GREEN 中间证据

本文件只覆盖 W5cam 第 2/6 步，**不是 verification，本波未完成**。

- RED：新增 `test_ecommerce_analyst_d01_issuer.py` 后先运行，因 `aos_api.ecommerce_analyst_d01_issuer` 不存在而 collection ERROR（`ModuleNotFoundError`），没有把该 RED 当业务失败或 PG 证据。
- GREEN：新增 `ecommerce_analyst_d01_issuer.py`。它只接收当前自然原链与完整治理后来源 reader 明确返回 True 的内部请求；核 running TaskRun、executing Task、approved Plan、三阶段顺序、D01 assignee、exact Task/Plan/Run 版本、稳定 AgentRun ID、最小来源 inventory；然后**只经既有 `AipAgentRunService.create`** 的稳定 key 建 queued AgentRun 并读回原 Receipt。unknown 原样抛出，不换 ID、不自动重发、不启动 Provider。
- 新专项 10 passed；与 W5cal Host/readiness、D01 worker/source/method 邻接累计 **106 passed、6 skipped、7 warnings**；`py_compile` 与 `git diff --check` 通过。测试正例是注入式无 DB 假件，不能证明来源 reader、真实 PG、Host 自动发行或首链。
- 剩余：当前原 Receipt→TaskRun 的生产 `require_current_origin`、同 cutoff Method/Eval/Metric/Query/EvidenceBundle/DisclosureGrant 的生产 `require_current_sources`、当前 route/budget/capacity 审计、隔离 PG 重启/重复发行、Host 接线与真实验收。真实 PG 当前没有 MethodRevision/running TaskRun，所以绝不能通过填固定 ID 或历史 Receipt 启动正向调用。
