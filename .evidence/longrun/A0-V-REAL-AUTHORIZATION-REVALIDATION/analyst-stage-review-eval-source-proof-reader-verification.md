# 阶段评审 Eval/source proof reader 验证

日期：2026-09-12

基线：`0ebb9f20`

结论：生成来源与 Eval 权威已能在事务一内只读生成 `validate_eval_proof` 和 `validate_structure_case` 两条 exact 消息，新 reader 不调用包；旧同步命令的 deriver 行为保持。

## 验证

- reader 继续核验 subject 父链、generation Artifact、成功 Attempt/Provider Receipt/usage、AgentRun/Skill/route/policy、唯一原 query Artifact、当前 EvalContract/Suite/Gate/Report。
- structure expected hash 来自当前 Suite 唯一 required positive case；Eval proof 绑定 tenant/artifact/attempt/contract/policy/cutoff/transaction now。
- snapshot 固定 Artifact、Attempt、AgentRun、request hash、query Artifact、contract/suite/gate/report、case hash 和时间；五个输出对象均 canonical JSON。
- 真实 portrait generation query 经 host reader 生成两条消息后，作者包 review operation 返回与 expected exact 相等。
- 旧 23 类来源/Eval 漂移拒绝保持；新 reader 在 deriver 被关闭时仍成功，证明事务内零包调用。
- 定向 `35 passed`；完整阶段评审 `180 passed`；compileall/diff check 通过。首轮扩大命令因测试路径拼写未收集，修正命令后全绿，未改代码。
- AR2-7 closure 扫描 1777、分类 140、迁移 93；所有错误数组为空。

## SHA256

- reader/compat command：`82d7507e3595dc0ac876583b553a5f5bb8a5e00c37eb76acb5fc9a1a1e76f6ee`
- tests：`325c748c7d184a79d0dd93bf7995b6a10321a13cf127a8b44d9fdf8d797d5b5b`
- plan：`da590537839750b346c7f60dc7690b9d74f0952df56a2f065c45ebc2bf3f2c23`

## 下一门

新增 composite authority reader，组合 command identity、responsibility proof、runtime proof、Eval proof、structure proof 为五个 `StageReviewValidationExchange` 和单一 authority snapshot；随后接 Owner binding 与双事务 coordinator，并实现 replay fast path。
