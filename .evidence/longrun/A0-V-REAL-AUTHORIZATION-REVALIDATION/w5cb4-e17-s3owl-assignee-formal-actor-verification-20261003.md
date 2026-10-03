# E17-s3o-w-l｜Assignee 写入口正式 actor 门验证

基线 `aos-platform/m1@4292eba2`、Authority `AOS-001220`。先读 231-1/5/9、W-L20、D-waves s3o-w-k、原 Assignee Router/Store 和 s3o-r/s 消费信任审计，再写同前缀文件级计划。当前真实库只读，未迁移、未启 Host/worker/Provider。仅修改两个 HTTP 写命令共用的 `_require_role`，要求正式 OIDC 与规范主体，原角色和租户取 Principal 逻辑保留。

| 门 | 命令与结果 |
|---|---|
| RED | `cd services/aos-api && uv run pytest -q tests/aip/test_e17_s3owl_assignee_formal_actor.py` → exit1，4 failed/2 passed：开发 Principal 与空白主体分别可触达 ToolBinding upsert、Assignee resolution 的 Store。 |
| 最小修复 | `routers/aip_assignee_authority.py` 在原角色门前拒绝 `token_kind != oidc`、空主体或首尾空白；`AIP_FORMAL_ACTOR_REQUIRED` 403。仅为既有版本冲突 HTTP 测试明确标注 test-only `token_kind=oidc`，不把该夹具当正式凭据。 |
| 专项 | `uv run pytest -q tests/aip/test_e17_s3owl_assignee_formal_actor.py tests/aip/test_e17_s3oq_tool_binding_issuance_pg.py` → exit0，10 passed。 |
| 相邻 | `uv run pytest -q tests/aip/test_w_l20_assignee_resolution.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_e17_s3or_tool_binding_source_receipt_pg.py` → exit0，8 passed/1 既有 strict xfailed；发行 Receipt 缺口继续 RED。 |
| 静态 | `python3 -m py_compile` 目标 Router/新测试；目标 `git diff --check` → exit0。无 UI/DB schema 改动，浏览器不适用。 |

复审：写命令仍只能使用 Principal 租户，两个请求没有自报 tenant；新门在调用 Store 前执行。代码仅收紧 HTTP Actor，原 Store 仍可由当前宽权限连接直接调用，ToolBinding 没有正式来源/同事务发行 Receipt/独立 issuer。当前无外部 OIDC 的实例会失败封闭；该测试的人工构造 OIDC Principal 只检路由条件，不证明当前真实身份、六 Binding、八配置或经营首链。Plan draft、Content 余额权威与 governed object verifier 的原来源缺口见同前缀 plan；BI issuer `SET LOCAL ROLE` 冲突仍单独待办。
