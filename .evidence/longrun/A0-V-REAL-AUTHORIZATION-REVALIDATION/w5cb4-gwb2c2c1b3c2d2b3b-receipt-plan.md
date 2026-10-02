# GW-b-2c2c1b3c2d2b3b｜原阶段 Review Receipt 独立来源合同

基线 `AOS-001127` / `m1 a5073009`。已复习 231-5 §1/§9、栖月汇六同事统一 Task/Handoff、BG00GW 清单。现有 Review Host 的 accepted-stage `revalidate` 会读原当前 Decision/获批 successor、BI Runtime、Stage Eval/permission 后失败关闭；`execute/verify_receipt` 仍关，`_accept_receipt` 只认识旧 ReviewIssue/四 Artifact。内容生成宿主 `_review_receipt` 同样只识别旧 Receipt。v3 Task/Brief 读者已能消费独立 expected，但 expected 尚无真实 Receipt 来源。

## 文件级顺序

1. `services/aos-api/tests/extension_runtime/test_ecommerce_content_generate_handoff_lineage.py` 先 RED：原 accepted-stage 命令 + Handoff/Task/Brief refs 生成 v3 ReviewDecisionReceipt，须含显式 `sourceKind` 和同一 17 项 `sourceLineage`，不含假 ReviewIssue/四 Artifact；改变 Decision/Artifact/markings 必改变 hash；旧 Issue Receipt 字段和 hash 不变。
2. `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py` 的 `_accept_receipt` 增严格 v3 分支，不开放 Host execute。内容生成 `_review_receipt` 后续须从原持久化 Receipt 读出并重建哈希、同源核 Handoff/Task/Brief/GrowthPlan 和单 Artifact；在该读者未完成前不把新 Receipt 接入真实执行路径。
3. 第二阶段用隔离 PG 的原 Receipt writer/Owner 联合正反测试，随后将 Receipt 来源传给 v3 Task/Brief 读者和原 Stage Owner 同事务复验；再接可读 Artifact 与人工评审。正式实例身份/八配置/Growth1.13/Host assignment 仍独立 P0。

本轮先实施第1项和 `_accept_receipt` v3 纯合同，专项/相邻回归、py_compile、浏览器禁入、verification、m1 精确提交及上下文同步。真实库只读，无商城源/旧Run/手工Run/dev-org写/Host/worker/Provider/push。不得把 Receipt 形状测试当真实人工批准或首链。
