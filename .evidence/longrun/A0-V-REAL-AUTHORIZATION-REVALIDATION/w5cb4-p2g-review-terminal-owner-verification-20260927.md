# W5CB4 P2g｜exact 评审 Receipt → 原 Run 终态 Owner（2026-09-27）

## 本波结论

- 新增 `ecommerce_content_review_step_owner.py`。受限选择器只提取当前安装/反馈/原 running Run 的 ACCEPT Receipt；`run_one` 由该 Receipt 与同一反馈 command 反建 strict command，在 serializable 九操作 Host 锁内再走 `ContentReviewHostService.revalidate` 与 `verify_receipt`。原 AIP Store 同事务写 `content_review` 的 think/act/verify/observe、StepRun/checkpoint 与 `complete_run`，独立连接复读 Receipt/反馈/Run/Task/TAOR；重复同 Receipt 只回读，不新增 attempt。无 Provider、外发或外部业务变更。
- 正式 `a0v_105` 一次性库中，原 Task/Run/已结算 Artifact/生成 StepRun/主体 Eval/Issue/模拟 ACCEPT/Host Receipt 保持同一对象。先用超管测试连接调用 `run_one`，数据库因缺 scoped runtime 身份拒绝且 review StepRun=0；补完整九操作 dispatch 后，以**非超级、serializable `aos_runtime`** 测试身份调用公共 `run_one`，原 review StepRun/TaskRun 正式终态，重复调用稳定；`CurrentFeedbackConsumer.list_pending` 随后出现唯一原 feedback command，之前不得出现。
- 该测试身份由一次性库连接切换而来，不是当前部署的真实 Runtime Host 登录。测试 Host Receipt 创建仍由受控 fixture 直接调用 service；责任模板 resolver 为测试接缝，非已签名 Bundle；reviewer/Provider/来源是受控材料。**未证明当前实例安装、真实人类审核、自然 review worker 或反馈目标真实消费**，不能称首链完成或放开生产。

## RED、最小修复与验证

- RED：九操作锁下非超级 `aos_runtime` 调用 Host `_artifact_authority` 遇 `permission denied for table aip_artifact`；全迁移库证实该不可变表给运行身份 SELECT、不给 UPDATE，`FOR SHARE` 触发额外写权限要求。只删 Artifact 查询行锁，保留 serializable、九操作锁、Artifact/hash/四来源 exact 查询；没有扩大数据库授权。
- RED：无 Receipt、双 Receipt、无完整 command、错 dispatch、被篡改的 RETURN 决定、非 runtime 身份均拒绝且没有新 review StepRun；已有 attempt 再完成被拒。测试内的漂移修改在 savepoint 回滚，未触当前业务库。
- 专项：新 Owner 单测 + 同库组合 `15 passed`。累计内容链/反馈选择器 `311 passed, 35 skipped, 7 warnings`；`git diff --check` 通过。纯后端阶段无需浏览器验收；跳过项不计为通过。

## 方案/代码复审与下一波

- 符合 231-5 的“人工评审 → 原 TaskRun 终态 → 反馈 pending”顺序，且只认原 ACCEPT Receipt、原 Run、当前 dispatch；RETURN 仍单独走新内部目标，不能伪造 succeeded。实施在用户授权的 `m1`，不 push、不动其他分支，不读商城源、不重发旧 12 Run/未知结果，230 L0 继续挂起。
- 下一波：默认关闭地接 Review 终态 Owner 的自然选择/worker，先实证当前 Runtime Host/签名模板和实例权限；在一次性库继续消费 feedback 第一段、读回 target Receipt/总控与 Wiki 候选边界。真实实例若缺合法签名 Bundle/人工决策，只保持 no-effect 并推进其余首链研发，不用模拟对象冒充业务完成。
