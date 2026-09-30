# W5CB4 BG00cq｜网络批准未知结果只读对账验证

## RED 与实现

接 AOS-000946，先读 231-4/231-5、BG00cj–cp 并写文件级方案。新增专项初次 RED 因缺 `aip_network_issuer_reconcile` 模块在收集阶段退出2。最小代码只接受 read-only 数据库事务、预期数据库名、真实 issuer session + runtime role、非 owner/非 superuser、精确事务租户；查询以 tenant/idempotency 参数化 SELECT 联结网络 Proposal，比较 proposal/requestHash/actor/当前 Proposal hash，返回 OBSERVED、CONFLICT 或 UNRESOLVED。无 Event 不表示可重发，代码无 INSERT/UPDATE/DELETE/`decide` 调用。

## 实测与回归

BG00cm 独立克隆真实 issuer TCP 连接在 `read_only=True` 下查询留下的测试 Proposal，Event0，结果 UNRESOLVED；可写连接先于 SQL 被 `READ_ONLY_REQUIRED` 拒绝，专项2 passed。当前真实库只读 owner 连接尝试同一核心，被 `ISSUER_READ_IDENTITY_REQUIRED` 拒绝、退出0的捕获脚本未写库。纯分类测试中精确行 OBSERVED，错 proposal/hash/actor/action/current hash 均 CONFLICT；这不是克隆真实 Event 正向。与合同/producer 邻接合计22 passed、2 skipped、7 warnings，退出0；`py_compile`、精确 diff check退出0。

## 未完成

本核心尚未挂独立进程或真实外部 OIDC 重验入口；正向 OBSERVED 只有纯分类测试，没有正式 Event 或真实 checker 证据。当前 HBA trust、issuer NOLOGIN、binding0，Host/worker/Provider关闭，首链待证。下波 BG00cr 做签发端 JWT/tenant/checker 重验及进程 IPC；未知/断联继续只读对账，不重发。无商城源读取、dev-org写、旧Run回放、手工run_definition、push。
