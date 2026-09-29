# W5CB4 BG-00j Artifact snapshot 来源元数据前检验证

方案见同目录 `w5cb4-bg00j-artifact-source-preflight-plan-20260929.md`。仅新增 `AipEvalPackRegistry.inspect_artifact_snapshot_source`，使用同一 scoped PostgreSQL 连接按 tenant/source ID/receipt ID 读取 `aip_artifact` 的 type/hash；该表无 revision 列，只接受 `1`。未接注册/Runner/发布，未返回正文、metadata、content_ref。`EvalDatasetManifest` 原合同继续校验字段白名单、case count、Receipt exact ref。

- RED：隔离 PG `test_aip_eval_pack_registry.py` 初跑缺方法，退出 1；修正测试负例 digest 后 GREEN。
- 专项与相邻：`test_aip_eval_pack_registry.py test_aip_eval_authority_api.py test_aip_eval_runner.py test_aip_release_publication_service.py test_aip_skill_publication_service.py`，退出 0，33 passed；最终新增负例后 Registry 专项 6 passed。测试在 `aos-a0v-test-only` 的隔离 schema 操作，不触碰当前权威库。
- `python -m compileall -q aip_eval_pack_registry.py` 与 `git diff --check` 退出 0。正例仅验证隔离 PG 的元数据精确引用；缺 source、缺 Receipt、跨租户、错 source/receipt hash、错版本/type 均失败关闭。
- 当前权威库 BG-00i 只读计数 source/Receipt 仍 0；本波没有真实库写入，也没有可成立的 D01 前检正例。

复审：这项只读前检不能证明 Artifact 内容真实、脱敏 Receipt 由获准 Owner 签发、字段值满足 allowlist，也不能证明 Judge/executor、Report/Gate 或首链。下一波须设计正式来源 Artifact/Receipt 生产者与签发权威，并让 Dataset 登记在同一受控事务中复核；当前静态 Registry 的旧登记方法仍不能作为业务发布入口。
