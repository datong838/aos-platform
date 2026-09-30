# W5CB4 BG00EF｜运行策略 kill switch 候选计数验证

按本波 plan 复习 231 主计划/231-1/231-3 与 BG00a/az/cx/ED 后，改动只在 `runtime_configuration_candidates.read_candidates` 的运行策略 count 上。`configuration_source_catalog.read_source_catalog` 已排除 active+kill；现与其对齐。未修改其它七类计数、API/页面、配置绑定或 Host 门。

| 检查 | 退出码/结果 |
| --- | --- |
| 初次沿 `test_configuration_source_catalog.py` 跑新用例 | 0，但 `1 skipped`，因为该文件要求额外 `AOS_EXTENSION_PG_TEST=1` 和 18432 专用 PG；不作为 RED/验收。用例已撤回，原文件无 diff。 |
| `pytest -q .../test_runtime_configuration_candidates.py -k killed_runtime_policy_is_not_counted_in_disposable_postgres`（改实现前） | 1；真实 pytest 临时 PG 中插入 active+kill 后，旧查询返回 1，预期 0；明确 RED。测试事务回滚，session 自动删除测试库。 |
| 同文件完整专项（最小实现后） | 0；4 passed。新用例证明 active+kill 不增加 count，active 且非 kill 才增加。 |
| `pytest -q test_runtime_configuration_candidates.py test_a0v_canonical_ecommerce_first_install.py test_configuration_authorization.py` | 0；36 passed，覆盖候选到首安装准入的相邻路径。 |
| `python -m py_compile` 两改动文件、`git diff --check` | 均 0。 |

方案/代码复审：SQL 条件与配置目录的 `r.payload->'killSwitchEnabled'='false'::jsonb` 相同；缺字段或 kill=true 不被报为候选。计数仍不是安装绑定、正式依赖、Host 或经营首链证明。真库只读，Host/worker/Provider 未开启；browser-pilot 工具本轮不可用，未形成浏览器截图，不以单元测试代替。另有 BG00ED 旧集成测试因 active NetworkPolicy 数据库门 RED，未由本波修复。

下波 BG00EG：继续独立检查八候选其他类别与配置目录/consumer 的一致性，仅挑可复现误报做最小修复；同时保留 E17 正式 signer/checker/Host Owner 与网络消费安全施工门。不得读商城源、写 dev-org、重放旧 12 Run、手工 run_definition 或 push；230 L0 挂起。
