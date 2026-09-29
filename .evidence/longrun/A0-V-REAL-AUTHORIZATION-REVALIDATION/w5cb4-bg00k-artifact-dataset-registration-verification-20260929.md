# W5CB4 BG-00k｜Artifact snapshot Dataset 同事务登记门验证

方案：`w5cb4-bg00k-artifact-dataset-registration-plan-20260929.md`。基线 `m1@6175d40a`，当日当前库 `aos_current_preview_20260927@a0v_111` 只读；所有写测试均在隔离 PostgreSQL schema/一次性克隆。新增门只针对 `sourceKind=artifact_snapshot`：Store 在插入 Dataset 的同一 scoped 事务内严格解析 Manifest，核同租户 source/Receipt 的 ID、类型、哈希及 revision=1。Registry 的 inspect 与登记共用此函数；`aos_runtime` 没有 UPDATE/DELETE，当前表有 append-only 与 truncate guard，普通 SELECT 不新增权限。

## 执行与输出

- RED：`pytest -q services/aos-api/tests/aip/test_aip_eval_pack_registry.py -k artifact_snapshot_source_metadata_preflight_is_scoped_and_exact` 在实施前退出 1：缺 source 时 `register_dataset_revision` 未抛错，说明旧入口能跳过只读 inspect。
- GREEN：`python -m pytest -q` 对 Eval Store、Registry、Runner、Release、Skill Publication、Content Pre-review、Content Review Pending 七文件跑 `-x`：退出 1，`52 passed, 1 failed`。唯一失败是交接时已存在的 `test_original_settled_artifact_runs_current_content_subject_eval[RETURN]`，在 `AipActionStore.create_proposal` 命中 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED`；这与本次 Dataset 来源门无关，生产禁入正确。该文件保留原有 +45 行审批链测试补强，本波仅给其隔离夹具补 exact source/Receipt 行。
- 同七文件加 `-k 'not test_original_settled_artifact_runs_current_content_subject_eval' --tb=short`：退出 0，`51 passed, 2 deselected`。单跑 `[ACCEPT]`：退出 0，`1 passed`。由此 52 个非已知 RED 的相邻用例均通过。
- `python -m compileall -q` 对本波七个 Python 文件：退出 0；`git diff --check --` 本波七文件：退出 0。

## 复审与限度

- Registry 正例的 source/Receipt 都是隔离库测试元数据；Store 直调缺 source 失败且 Dataset 行 0。跨租户、类型、哈希、revision 漂移的 inspect 负例继续通过，共用门阻断登记。相邻两个既有正式链测试的夹具补入对应隔离 Artifact 元数据，没有给当前库制造来源。
- 当前正式签名包仍为 `evals/placeholder.json: BLOCKED`；当前栖月汇 D01 不存在合法 Artifact/Receipt。此门不核内容字节、字段值、脱敏签发 Owner 或撤销，也没有正式 Judge/Target executor；因此不声称正式 Eval、Skill 发布或经营首链通过。
- 已知独立 RED 的返工 Action 需要现时 Capability/预算/安装绑定来源。禁止用测试占位或高权限路径让它变绿；下一波继续补可独立实现的正式来源 producer 合同与只读审计。
