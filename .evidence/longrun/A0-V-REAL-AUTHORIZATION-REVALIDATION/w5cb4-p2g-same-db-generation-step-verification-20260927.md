# W5CB4 P2g｜同一原结算结果的生成 StepRun/checkpoint 子证明

- 基线 `m1@134387e3`；方案先行，改动仅限 P2g plan、本文件与 `services/aos-api/tests/extension_runtime/test_ecommerce_content_review_pending_pg.py`。复用一次性克隆库的正式 `a0v_105` Alembic 升级、同一原 Task/Run/Reservation/command/runtime Receipt 和受控本地结果；没有迁移当前业务库，也没有 Provider 网络调用。
- 正向：原 `ContentResultConsumer` 持久化的 settled Artifact、Provider Receipt 和两条 Usage Receipt 经 `ContentGenerationStepSource.read` 读出；`ContentGenerationStepOwner._complete_transaction` 通过正式 AIP Store 在同库写 `content_generate` 的 think/act/verify/observe 四相、唯一 `attempt=1` 的 succeeded StepRun 与 checkpoint。另一连接 `_readback` 验证原 Run、StepRun/checkpoint；独立 SQL 验证 observe 中 exact Reservation/Artifact 引用。重复原证明只读回既有成功步，不新增 attempt。
- 负向：业务 context 提供错误 Run 引用时，正式 Source 因 Artifact 不属于该原 Run 而 `ContentStepConflict`，StepRun 计数仍为 0。此前结算失败事务回滚子证明保持有效。业务 context、prepare 与 Provider 响应是显式受控接缝；没有把测试 fixture 说成真实商城/方法来源。
- 专项 `1 passed, 4 deselected, 7 warnings`；内容、通用 EvalRunner 与邻近 PG 文件累计 `292 passed, 35 skipped, 7 warnings`；`git diff --check` 通过。纯后端事务证据，浏览器验收不适用。生产 `run_one` 所需九操作完整 Host 锁、非超级用户身份和 serializable 隔离未组成，故未调用自然 worker、未启生产，不声称正式外层执行授权。
- 下一波：在同一原 Artifact 上接当前 EvalContract/Plan gate 的正式主体 EvalRunner，再验证 pending review 候选；先复习产品/技术方案及合同注册约束，缺少合法权威时保持 no-effect，不开放 Issue/GET。
