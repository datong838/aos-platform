# E17-s3m AssigneeResolutionReceipt subject 门验证

基线 `m1@7d8e88b2`、Authority `AOS-001183`；当前真实库 `aos_current_preview_20260927@a0v_135` 只读。本波仅用 `disposable_database()` 隔离克隆验证，未对真实实例创建 Plan、Receipt 或业务动作。

## 方案与 RED

- 上位 49-W6-01 ADR 要求职责槽、候选 Assignee 和 exact capability 形成解析 Receipt；115 的工作台读模型要求任务/计划/slot 的 subject 精确匹配。
- 原 Plan 消费 `_require_exact_assignee_resolution` 未读取 Receipt `subject_id`。新增 `test_resolution_receipt_for_another_subject_cannot_authorize_plan_slot` 用原 resolver 产生 `analyst.portrait.review` Receipt，再借给 `analyst.other.review`。旧生产代码下 Plan 成为 READY，断言失败（RED，pytest 退出码 1）；说明同一人、空 capability 不能代替槽位授权。
- 相邻旧 `test_responsibility_plan_accepts_fresh_canonical_provider_resolution` 曾用 `responsibility-plan:w2b/slot:content.review/<随机值>`，既不符合其 Plan 创建所用 `content.review` 槽位 ID，也不符合 115 的正式 `planId@revision/slotId` 格式。按方案把夹具 subject 改成 `content.review`，保留原 Provider、Binding、Capability 断言；不修改生产 resolver 或 DB schema。

## 最小实现与复核

- `services/aos-api/aos_api/aip_production_contract_store.py` 原 tenant+Receipt SELECT 增读 `subject_id`，对当前 Plan slot ID 不同的 Receipt 抛 `ASSIGNEE_RESOLUTION_SUBJECT_DRIFTED`。创建依赖预检前拒绝，Plan head 计数和 create Receipt 不增；原 `content.review`/`analyst.portrait.review` 正向保留。
- `services/aos-api/tests/test_ecommerce_analyst_stage_review_authority.py` 新隔离负例；`services/aos-api/tests/test_w2b_production_contract_store.py` 修正上述旧夹具。未改 API、迁移、前端或 Host 启用门。

## 运行结果

| 命令（在 `services/aos-api`） | 结果 |
| --- | --- |
| `.venv/bin/python -m pytest -q tests/test_ecommerce_analyst_stage_review_authority.py tests/aip/test_w6_01_exact_assignee_resolution.py tests/aip/test_w_l20_assignee_resolution.py tests/test_w2b_production_contract_store.py --tb=short` | 退出 0；35 passed，7 warnings |
| `.venv/bin/python -m pytest -q tests/extension_runtime/test_ecommerce_content_review_pending_pg.py tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py --tb=short` | 退出 1；1 failed，22 passed；旧 `RETURN` 正向走 `AipActionStore.create_proposal`，被当前正式 `REPAIR_ACTION_CURRENT_AUTHORITY_UNWIRED` 门拒绝 |
| `.venv/bin/python -m pytest -q tests/extension_runtime/test_ecommerce_content_review_pending_pg.py tests/extension_runtime/test_ecommerce_content_review_authority_feedback.py tests/extension_runtime/test_ecommerce_content_repair_action_binding.py -k 'not test_original_settled_artifact_runs_current_content_subject_eval' --tb=short` | 退出 0；32 passed，2 deselected；含当前返工 Action 失败关闭测试 |
| `.venv/bin/python -m py_compile aos_api/aip_production_contract_store.py tests/test_w2b_production_contract_store.py tests/test_ecommerce_analyst_stage_review_authority.py`；`git diff --check` | 均退出 0 |

## 未解除的门

旧 `RETURN` 正向用例与后置 fail-closed 生产合同冲突，不能借本波跳过返工正式来源门；登记后续独立修复/重定验收。运行 DB 角色仍能直接写 Binding/Registry Receipt；Assignee 当前成员撤销/Binding 变化、正式六绑定、八有效配置、Host assignment/Owner 与首链仍未证明。此波证据只证明隔离代码门，不是当前实例安装、运行或业务闭环通过。

## 提交后在线回读（同日完整重启之后的 API 局部重载）

- `m1@35c66547` 后原签名启动器预检退出0：`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，库 `aos_current_preview_20260927@a0v_135`、安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` approved、publishedVersions4、runtimeBindings0。独立备份 SHA256 `e2c3a4b6881e5b4616b92ce42052227d6a20fa34b4310debcda83c939c9e04a0` 再核一致。
- 原 launchd API 项 `bootout` exit0，确认8080退出，原 plist `bootstrap` exit0；API PID35024，PG映射18435、Web31986/8434仍在，18181无监听。`/v1/health`、`/v1/ready`、`/openapi.json`、`/aip/skill-publish` 均 HTTP200；首次用错误的无 `/v1` 健康路径得到404，已按 Router 实际路径纠正。启动日志 `migrationMode=disabled`、`runtimeHost=0`、`workersEnabled=0`、Host inactive `DISABLED`。
- CUA 原浏览器 `org-org/dev-project` 的技能发布页回读：37条仅已评测、0已发布，三个来源 blocker，发布按钮 disabled，工作台无可见电商入口。浏览器截图已在本轮 CUA 输出取证；没有真实 Plan/Run 写入。
