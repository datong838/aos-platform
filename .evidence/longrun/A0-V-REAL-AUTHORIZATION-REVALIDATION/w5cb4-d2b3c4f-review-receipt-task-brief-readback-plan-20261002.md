# d2b3c4f 新来源持久 Receipt→Task/Brief 同截面读回计划

基线：`m1@d2bf1da8`、`AOS-001158`。上位 `231-工作台业务闭环长程开发路径与波次实施计划.md`、`231-3-安装启停卸载重装状态机与接口实现方案.md`、D-waves d2b3c4f。只在隔离 PG 验证读者；当前真实库只读，Host/worker/Provider 关闭。G2 正式 Eval 原生产者与当前实例正式身份仍缺，故本波不删除 `accepted stage Handoff ... is not wired` / `accepted stage Handoff Owner is not wired` 禁入，不宣称原生产者正向或自然首链。

## 缺口与最小文件包

`ReviewAdvanceHostService.verify_receipt` 对 `accepted-stage-v1` 已核对持久 Receipt 的 ID、自哈希、requestHash、17 项 sourceLineage、ACCEPT 与零副作用，但尚未回读 Receipt 指向的原 Task/Brief；持久 Receipt 与缺失或漂移的 Task/Brief 可被单独当作验证成功。原 `_review_lineage` 使用 `AipTaskStore.create_task` 与 `AipProductionContractStore.create_brief` 在同事务持久化。`ContentReviewHostService._task_brief_authority` 已有相应 Task/Brief exact ref/hash/绑定读者，可复用。

- 改 `services/aos-api/aos_api/ecommerce_growth_runtime_adapters.py`：仅在新来源 `verify_receipt` 的 Receipt 自身校验成功后，复用 `_task_brief_authority` 核对原 Task/Brief，并追加 Task.goal 与 Brief.spec 的 `sourceLineage`、`sourceHandoffRef`、单原 Artifact、v3 schema 与外部发布禁用同截面核对；任何异常返回空验证结果。旧四来源与发行/执行入口不变。
- 改 `services/aos-api/tests/extension_runtime/test_ecommerce_review_task_brief_authority_pg.py`：在可销毁 PG 用原 `_review_lineage` 写 Task/Brief，模拟仅本测试的 Receipt 读回，先 RED：Receipt 指向缺失或伪造 Task/Brief exact ref 时 `verify_receipt` 必须返回空；完整同事务读回才返回原 Receipt。测试角色无 UPDATE 原 Brief 的权限，故不通过提权改表制造 drift。测试不作为正式 G2/Review producer 业务通过证据。
- 改 `services/aos-api/tests/extension_runtime/test_ecommerce_review_advance_host.py`：旧单元正例若仅有伪 Receipt 而没有原 Task/Brief，改为必须失败封闭；保留错租户/key/Decision/hash 负例。
- 相邻回归暴露原有 Stage fixture 的批准时间取宿主钟，而来源时序门取数据库钟；本机实测宿主批准时间比同次数据库钟快约 65 ms，独立重跑原有 Stage 测试也失败。最小修复限 `services/aos-api/tests/extension_runtime/test_analyst_stage_handoff_source_pg.py` 的测试批准时钟注入，改用同一隔离 PG 的 `clock_timestamp()`，不改产品时序门；先保留 RED 输出，再复验原测试与相邻回归。

预读 SHA256：runtime adapters `566e5e37fcd1e487714e202c8462f94d86c6434315842e259bd887f38eccfc5d`；PG test `851d3f640a57588a87499706d793fba62c02fca2f65287dd58182fb54efc456e`；unit test `610005715654b5aae7ef09dc4ba1194b6577032837d0b4a4527f2da8a525637e`。先运行单个 RED，再最小实现、专项和相邻回归；语法、diff、禁入分支及浏览器仍需复核。数据库测试限 `aos-a0v-test-only`，保留测试库，不删任何库/卷/备份。回滚只撤销本波代码，不改变真实安装与数据。
