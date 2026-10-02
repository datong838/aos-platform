# W5CB4 E17-s2b｜最终 Skill 发布稳定事务验证

## RED、最小改动与复审

- 已先读 231 主线、E17 上位方案、原 SkillPublication/ReleaseGate 调用及本波文件级方案。原最终发布使用 read-committed 默认连接，无法满足签名证明读取器要求的稳定租户事务；隔离测试先命中 `Skill Eval tenant snapshot is unavailable`。历史未签名报告不作为正向验收。
- `aip_skill_publication_service.py` 仅将最终 `publish_evaluated_revision` 的默认连接改为 `connect_serializable(scope)`；显式注入的连接保持原样，由证明读取器拒绝不合规隔离级别。原锁、幂等 Receipt、Gate/Event、Logic/Route/Policy 和新修订写入顺序未改。
- RED 又发现 E17-s1 装配的 `except ValueError` 会包住其子类 `EvalExecutionRejected`，模糊实际禁入原因。`aip_eval_report_proof_reader.py` 先透传此异常，仍失败关闭；没有新增放行路径。

## 可复核结果

| 验证 | 结果 |
|---|---|
| 最终发布缺侧证负例 | `tests/aip/test_aip_skill_publication_service.py::test_final_skill_publication_rechecks_evidence_in_stable_tenant_snapshot`：1 passed，exit0；错误链到 `EvalExecutionRejected` 且含 `sidecar`，新发布 Receipt=0。 |
| 相邻回归 | 从 `services/aos-api` 执行 `AOS_DATABASE_URL='postgresql://aos_app:aos_dev_only_change_me@127.0.0.1:18435/aos_current_preview_20260927' .venv/bin/python -m pytest -q tests/aip/test_aip_skill_publication_service.py tests/aip/test_aip_release_publication_service.py tests/aip/test_aip_release_publication_signed_skill_pg.py tests/aip/test_aip_eval_report_persisted_assembly_pg.py`：23 passed，1 xfailed，exit0。测试只使用 conftest 的临时 `aos_test_*_ti4_test` 库；原 xfail 不计通过。 |
| 静态及改动 | 三个目标 Python 文件 `python3 -m py_compile` exit0；`git diff --check` exit0。其余浏览器插件、锁文件和历史证据的既有工作区改动未纳入本波。 |

## 未完成与风险

- 原测试夹具的历史成功 Report 无正式双签，本波只证明最终发布事务到达签名门且正确失败关闭；**尚未完成原 evaluated Skill、签名 Run/Report、PASSED Gate、PublicationEvent、Logic/Route/Policy 到新 published Skill/Receipt 的隔离正向链**。不能宣称真实 Skill 发布或首条经营链完成。
- 当前正式 issuer/Target/Judge、Run Owner、受限 writer 与六 active Binding 尚未齐备；当前真实库只读、Host/worker/Provider 关闭。下一波可独立补隔离正向生产者与消费者联测，正式实例缺身份仍局部禁入。
