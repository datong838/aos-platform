# GT-b2 Model 首评候选 PostgreSQL 行锁验证计划

基线 AOS-001085 / m1 `ea173ef1`。Task `W5CB4-GTB2-MODEL-EVAL-PG-HEAD-LOCK-20261002`。复习 231-5、BG00GT、GT-b1 方案及 `AipModelRuntimeStore.require_current_model_eval_candidate_for_update`。真实权威库只读；仅现有 test-only PG 的测试专属 Model 记录允许写入与回滚。

本检查点只修改 `services/aos-api/tests/aip/test_aip7_model_runtime_store.py`：在现有发布 Model 的临时身份与 cleanup 内，用两个独立数据库连接验证调用方事务持有 Model head `FOR UPDATE` 后，另一连接以有界 `lock_timeout` 请求同一 head 锁必失败；第一连接结束后相同锁可获取。再在同一测试事务内变更 head version 后调用 reader，确认旧 expected version 失败，回滚不污染后续测试。使用当前 Model 的 source/next-active target，不构造伪 Task/AgentRun、不调用 Provider。

本波是对上一波已有 reader 的 PostgreSQL 语义补证，不新增生产逻辑；不能伪造一个 RED。以两连接争锁超时和释放后成功作为差异判据，再跑专项及相邻 Model/GT-a 回归、编译与 diffcheck；记录使用的数据库连接地址与角色类型但不输出凭证。若测试连接指向当前权威库立即中止。此测试只证明锁定读事务语义，仍不代表 maker/checker、预算容量、发送 intent 或首评可执行。
