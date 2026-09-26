# W5CB4 P2f-b 第 3/4 步｜当前内容 Eval 权威与原 Plan 门验证

## 边界与结论

- m1 单写；只修改内容预审权威读取器、TaskRun Owner、邻近测试和本方案/证据。未读商城源数据，未操作原 12 Run、230 L0、Provider、外部发布或当前生产元库。`dev-org/dev-project` 仅为隔离零 canary。
- **部分代码门通过，非自然业务链 GREEN**：当前实例 `aos_meta_head` 上次只读见 `a0v_092` 且内容主体 EvalContract 为 0；本步没有迁移、注册正式包、开启 Worker 或运行真实内容 Artifact Eval。浏览器验收不适用（无 UI 改动）。

## 方案与文件级实施

- 依据 231-5 §1/4/5、231-9 BG-04、栖月汇数字同事产品方案及 `w5cb4-p2f-original-plan-content-eval-authority-plan-20260926.md` 第 3/4 步。内容生成模型的自评合同不等于产物审核合同；不能由任意 READY 行推出授权，也不能事后改写旧 Plan。
- 新增 `services/aos-api/aos_api/ecommerce_content_pre_review_authority.py`：同租户单事务内取唯一 current 内容合同，核其冻结 READY、canonical hash/审核策略、当前 Graph 规格/哈希、治理及主体 Suite、同 exact target 的 ReleaseGate/Publication/报告/Run 与 DB 时钟有效期；缺失、多义、漂移、撤销、过期均失败关闭。
- 修改 `services/aos-api/aos_api/ecommerce_content_taskrun_owner.py`：claim 前预检，缺权威不消耗 attempt；execute_claim 原事务重验并把 exact EvalContractRevision 写入**新建** Plan 的唯一 `content_review.gateRefs`；独立提交后读回还核该 exact gate。读回未知则冻结，不重发。
- 测试仅在 `services/aos-api/tests/extension_runtime/test_ecommerce_content_pre_review_eval.py` 与 `test_ecommerce_content_taskrun_owner.py` 增加正反路径；原 Plan 和原 Run 不补票。

## RED→GREEN 与验收

- RED：新权威读取器导入失败；缺 current 内容权威时 Owner 旧行为会进入 claim；提交后 Plan gate 漂移反例原逻辑接受。GREEN：三类反例均失败关闭，正向隔离正式 API 链可返回 exact ref。
- 累计命令：`PYTHONPATH=services/aos-api services/aos-api/.venv/bin/pytest -q services/aos-api/tests/extension_runtime/test_ecommerce_content_*.py services/aos-api/tests/test_ecommerce_content_eval_plan_gate.py services/aos-api/tests/test_aip_ecommerce_content_eval_input.py`；结果 **258 passed，9 skipped，7 warnings**。9 skipped 为需专用 PG opt-in 的测试，不作通过证据；7 warnings 为现有 Pydantic/Starlette 提示。
- `git diff --check` 通过。方案/代码复审：只绑定结构/来源完整性预审门，不能称事实/合规审核通过；人类 exact 评审及实际 Artifact 主体 Eval 仍属后续波次。无 UI，故不制造浏览器绿色验收。

## 余险与下一步

- 当前实例未安装所需 schema 与内容预审包，因而新 TaskRun 正常失败关闭；不能由隔离 PG 成功推断生产可用。正式安装还需可重入 bootstrap、唯一当前合同、权限/迁移预检、实例读回及安装/恢复边界。
- 下一步 P2f-b 第 4/4：先完善受控安装方案与只读预检，再最小实现和隔离验证；没有当前实例确证，不开启自然 Worker。完成本段后才进入 P2g 的真实已结算 Artifact→主体 Eval→待办/人类决定→Run/反馈续跑。
