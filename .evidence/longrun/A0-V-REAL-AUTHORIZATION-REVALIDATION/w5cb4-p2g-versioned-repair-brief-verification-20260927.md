# W5CB4 P2g27 · RETURN 新版 Brief 正式来源验证（2026-09-27）

## 方案与改动

- 先复习 231-5 §4/5、P2g26 禁入门和公共 `AipProductionContractStore.revise_brief`；`m1@886f2550` 方案先行，发现现有同库 RETURN 链可复用后于 `m1@c80df8ed` 追加确切测试文件范围。
- 新增 `ecommerce_content_repair_brief_authority.py`：只读核同一 Task 的当前 Brief revision、紧邻前版、公共 `task_brief.revise` Receipt/requestHash/resultRef、原 spec 与人类 RETURN 的 exact Decision、原 Artifact/hash、理由。只允许在原 spec 上追加唯一 `repair` 段，不改变来源/外部发布请求。旧版、伪 Receipt、错 Task/Decision/Artifact/理由及 revision 漂移全部拒绝。
- `ContentGenerateHostService._return_authority` 在正式退回、最新 queued StepRun 与新批准时间门后接此只读证明；P2g26 的 `revalidate/execute` 双重返工禁入保留不变。首次生成命令和路径未扩权。

## 新鲜证据

- RED：新模块缺失导致测试 collection 失败；加入模块后，新增 Host 调用断言因无入口失败，随后最小接线转 GREEN。
- 在 `a0v_106` 一次性完整迁移库，同一原 Run/正式 RETURN/原 Artifact 上经公共 `revise_brief` 生成 revision+1 和 Receipt；非超级 runtime 身份在 scoped 连接里读回 exact 证明。拿此新版 Brief 配原批准，Host 仍按“新批准不足”拒绝，无预算、Provider 或新 StepRun 效果。`RETURN` 专项 1 passed。
- 新模块+Host 专项 21 passed；八组相邻累计 **91 passed**。`compileall`、`git diff --check` 通过，Alembic 唯一 head `a0v_106`。`dev-org` 未作为正租户；当前 8080/18181 无监听。纯后端且当前真实恢复库不可安全启动，本波浏览器验收不适用。

## 边界、风险与下一波

- 该新版 Brief 是受控测试原对象链的准备证据，不是当前真实人类返工，也不是执行许可。它刻意保持原业务来源不变、把退回原因和原 Artifact 纳入新版修订；如果产品要求修改核心来源/目标，须另走新的上位评审和批准，不能借此最小切片隐式改写。
- 新批准提案须绑定新版 Brief/ReturnDecision/当前安装及费用上限，随后才可建立全新容量和预算 reservation；Provider 用的 prompt、版本产物、attempt=2 settled 结果 Owner 尚未实现。下一波先落实这些权威的正式生产者与同库负例，双重禁入在全链证明前不解除。
- 当前恢复 PG 仍为旧 `a0v_092`、缺当前可核备份，继续 `STOP_MIGRATION / STOP_CURRENT_API_AND_WORKERS`；不读商城源、不重放旧十二 Run、不手工 `run_definition`，未知结果不重发。用户自有两份 `w5c8i-test-only-*` 文件未触碰。
