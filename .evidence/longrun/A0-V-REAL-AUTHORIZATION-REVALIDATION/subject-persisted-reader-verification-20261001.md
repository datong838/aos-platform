# Subject 持久证明读取波验证

基线 m1 5b19bc98，AOS-001076；目标仅为当前空表与原 EvalRun 的同事务读证，不建立正式 issuer、writer 或自然业务授权。方案：`subject-persisted-reader-plan-20261001.md`。

## RED / GREEN

- RED：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_subject_persisted_reader_pg.py`，退出码 2，`ModuleNotFoundError: aos_api.aip_eval_subject_persisted_reader`。
- GREEN：同命令退出码 0，15 passed。标准 session fixture 建立并自动删除 `aos_test_*_ti4_test`；未连接当前真实库。测试专用 Ed25519 签名、同租户 succeeded EvalRun、root/identity/Receipt 正向读取；缺行、跨租户、错误角色/隔离级别、root/identity 撤销、旧用途、Run/封套/Receipt 漂移、未来落盘均拒绝。
- 相邻回归：`services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_eval_subject_persisted_reader_pg.py services/aos-api/tests/aip/test_aip_eval_subject_persistence_pg.py services/aos-api/tests/aip/test_aip_eval_subject_signature.py services/aos-api/tests/aip/test_aip_eval_subject_proof.py services/aos-api/tests/aip/test_aip_eval_execution_authority.py services/aos-api/tests/aip/test_aip_eval_report_context.py`，退出码 0，124 passed；10 warnings 是原字段/测试异常值告警。

## 方案一致性、风险与下一步

新 reader 要求 `aos_runtime` 与精确租户 GUC、repeatable read/serializable，查询同一事务内 EvalRun、subject-review root/identity、两条不可变 Receipt 和撤销记录，再调用双签验证。只返回结构证明，不创建 Run/Report、发证、发 Provider 请求或放行 Host。原 eval-execution reader/迁移未改；本波无前端变化，浏览器验收不适用。

尚未把 query/subject 原字节、生成 AgentRun/Usage、安装代次/配置、Eval Case、原 Report/Stage 消费与正式 Owner 一起读证；当前真实库 a0v118 只读且代码头 a0v131，不能做最新系统重启或称业务完成。下一波先复习原 EvalRun 创建与生成来源 Owner，制定受限 writer/Report 同事务方案，接原阶段消费者；正式身份与实例迁移另走安全门。测试 seed 不作为真实经营证据。
