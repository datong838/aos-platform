# W5CB4 E17-s3c｜原 Logic Eval 证据生产链文件级方案

## 上位合同与本波范围

- 按 231、E17-s3b，Skill 发布的 LogicRevisionRef 只能指向原 `LogicPublicationStore.publish` 的持久发布行。该发布必须消费当前 Graph immutable revision、成功无生产写 dry-run，以及同租户同版本原 Eval 报告。
- 当前 `test_aip_logic_publication_store.py` 的正向测试用 `FakeEvidenceReader` 直接写 Suite/Report，不能证明原 Eval 生产链。生产路由使用 `aip_eval_store.LogicEvalEvidenceReader`；`routers/evals.py` 的 `_run_and_persist` 经原 dry-run executor、EvalEvidenceStore 保存报告。
- 本波仅在隔离 PG 验证原 Graph → dry-run → Eval Suite/Run/Report → LogicPublication 正反链，不写当前真实库，不开启 Host/worker/Provider，不触碰商城源或旧 Run。

## 文件级实施

1. 先在 `services/aos-api/tests/test_aip_logic_publication_store.py` 增加默认读者缺报告的失败封闭断言（publication=0），作为 RED 边界。
2. 在同文件以现有隔离 schema 和原服务建立 Graph、成功 dry-run、原 Eval Suite，调用 `routers/evals.py::_run_and_persist` 生成持久 Report；以生产 `LogicEvalEvidenceReader` 发布 Logic。核同租户 exact Graph 版本、dry-run id、Report id 和 publication 行，异租户/错 Report 拒绝并保持原行数。
3. 只在该链揭示真实生产缺陷时，另起精确文件级方案与 Lease 才改生产文件。本波不为测试绕过原门。
4. 专项及相邻回归、方案/代码一致性复审、verification 和 m1 精确提交；随后更新 AOS/Prime 上下文及 D-wave 下一项。

## 验收边界

隔离测试通过仅证明 Logic 原代码链可用；当前实例的正式 Skill Eval issuer/Owner、Route/Policy、八配置和首条经营链仍需独立正式证据。
