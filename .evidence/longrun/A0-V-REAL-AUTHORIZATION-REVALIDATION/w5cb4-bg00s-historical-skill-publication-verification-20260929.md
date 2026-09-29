# W5CB4 BG-00s｜历史 Gate/Event 不能再发行 Skill 修订

方案 `w5cb4-bg00s-historical-skill-publication-plan-20260929.md`，基线 `aos-platform/m1@0efe6191`、权威 `AOS-000867`。代码只改 `aip_skill_publication_service.py`，测试只改 `test_aip_skill_publication_service.py`；没有迁移或当前业务库写入。

## 现场与 RED

- 当前 `aos_current_preview_20260927@a0v_111` 在 `BEGIN READ ONLY` 下回查：栖月汇 Gate/Event 0、全库 published Skill 0。不存在本波需对账的已发生再发行；这不证明代码未来安全。
- 现有服务在同事务核了 evaluated source、Gate passed/exact target、最新 Event published/exact target，再验证 Logic/Route；缺 Report 的真实执行来源复核。隔离 PostgreSQL 用 `test-only://` Artifact 与 lambda 创建旧 Skill Report，并精确种下历史 PASSED Gate + published Event。RED 命令 `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_skill_publication_service.py::test_historical_unattested_skill_event_cannot_mint_new_skill_revision` 退出 1，`Failed: DID NOT RAISE AipAgentRegistryTransitionBlocked`，说明原代码确实会再发行。

## 最小实现与核验

- 服务仍在同一个 scoped transaction 精确核 Gate/Event；读取完整 Gate 行后复用 E2 的 Gate/Report 复验。当前 E2 对无独立 Judge/Target signer/执行 Receipt 的 Skill 失败封闭，转换为 Skill publication 的 `AipAgentRegistryTransitionBlocked`，发生在 Logic/Route 调用、新 Skill revision 和 RegistryReceipt 插入前。同 key 已有 Receipt 回放原路径未改，历史 Gate/Event/Skill 没有删除。
- RED 转 GREEN 的两项负向测试 `2 passed`、退出 0；Runner/Registry/E2/Skill 发布/Skill Binding 相邻累计 `34 passed, 1 xfailed`、退出 0。严格 xfail 仍是缺正式执行权威的旧 lambda 正向链，不能称为验收通过。两文件 `compileall -q` 与 `git diff --check` 均退出 0。
- 当前权威库再次 `BEGIN READ ONLY` 核 `a0v_111`、published Skill/Gate/Event `0/0/0`；未读商城源、未启 Host/worker/Provider、未重放旧 12 Run、未动 230 L0。

## 限制

此波堵住“历史 Event → 新 published Skill 修订/Receipt”。`AipSkillBindingReadinessService` 对**已经存在**的 published Skill 仍仅浅核 Gate/Event 的状态与引用；当前库没有这类修订，但隔离或未来恢复的历史行仍需下一波独立审计。正式 Judge/Target signer/撤销/执行 Receipt、G2 内容 Owner 与 BG-00o 真实 S3 回环仍缺，正向 Skill 发布和自然首链没有完成。
