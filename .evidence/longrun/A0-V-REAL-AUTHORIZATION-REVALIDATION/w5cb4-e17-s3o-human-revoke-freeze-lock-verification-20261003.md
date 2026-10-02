# E17-s3o-a 真人撤销与 Plan 写准入并发行锁验证

基线 `aos-platform/m1@3bb69820`、Authority `AOS-001185`。上位 231/231-9、49-W6-01、115 exact subject 与 s3n 方案已复核。只在 `disposable_database()` 的 org-org/dev-project 克隆库执行成员删除和 Plan 冻结；真实库 `aos_current_preview_20260927@a0v_135` 只读，Host/worker/Provider关闭。

## RED 与最小点

新测试创建原 Resolver Receipt/READY draft。连接 A 执行 freeze 共用 `_require_responsibility_dependencies` 后保持写事务；连接 B 以 `lock_timeout='250ms'` 删除同租户同成员。旧码 B 删除成功，`pytest.raises(LockNotAvailable)` 未触发，RED exit1。说明仅在写前普通 SELECT 成员，不保证到冻结提交前仍有成员资格。

生产改动仅在 `_require_responsibility_dependencies` 调用原 Receipt 检查时传 `lock_human_membership=True`；`_require_exact_assignee_resolution` 只对 HUMAN_PRINCIPAL 且写准入使用 `FOR SHARE`，其余调用保留普通 SELECT。GREEN 证明 B 在 A 提交前锁超时；A 同一事务完成原 freeze 后，独立 read-only 连接 GET READY；A 提交后 B 正常删成员，再以 read-only GET 回读 BLOCKED。原 Stage Review 执行门仍另持成员锁。未修改三种机器 assignee、Receipt 历史、DB schema 或真实租户数据。

## 本次命令与结果

| 命令（在 `services/aos-api`） | 结果 |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/test_ecommerce_analyst_stage_review_authority.py -k write_admission_holds_member --tb=short` 修复前 | exit1；`DID NOT RAISE LockNotAvailable`，RED 成立 |
| 同命令修复后 | exit0；1 passed，10 deselected；删除确实被 Plan 写事务挡住，read-only GET 仍能工作 |
| `.venv/bin/python -m pytest -q tests/test_ecommerce_analyst_stage_review_authority.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_w_l20_assignee_resolution.py tests/test_w2b_production_contract_store.py tests/extension_runtime/test_ecommerce_content_repair_action_binding.py --tb=short` | exit0；48 passed、7 warnings |
| `.venv/bin/python -m pytest -q tests/extension_runtime/test_ecommerce_content_review_pending_pg.py tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py -k 'not test_original_settled_artifact_runs_current_content_subject_eval' --tb=short` | exit0；21 passed、2 deselected；旧 RETURN 正向与当前返工来源门冲突承接独立待办 |
| `py_compile` 两个改动 Python 文件；`git diff --check` | 均 exit0 |

## 边界与下波

行锁只保障 Plan create/revise/freeze 写事务的真人成员检查到提交之间不被并发删除；GET/list 继续只读判断，提交后的撤销会让 Plan 重新 BLOCKED。角色/ABAC/容量、机器 Binding 撤销当前性、Receipt 独立签发 ACL、旧 RETURN 正向冲突、六正式绑定、八配置与自然首链均未由本波证明。不能因这次隔离 GREEN 启动 Host。
