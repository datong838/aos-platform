# Subject 持久证明读取波文件级方案

基线 m1 5b19bc98 / AOS-001076。用户已批准 subject-review 的设计、编码和隔离测试；当前真实库 a0v118 只读，代码头 a0v131，不能对当前库迁移、写入或启动 Host/Provider。本波按 AGENTS、aos-engineering-delivery 和 231 首链方案执行。

## 输入与边界

原 `aip_eval_persisted_authority_reader.py` 只处理 eval-execution target/judge，不改变其语义。a0v131 新表是空的 append-only subject Receipt 存储；仅有表/签名对象不构成实际 Owner、生成来源或评测权。`aip_eval_run` 已含 suite、target、judge、合同、subject、stage、policy 与 cutoff 元数据；其余 query 原字节、生成 AgentRun/Usage、安装 fence 仍须后续 Owner 逐项读取。

## 精确改动

1. 新增 `services/aos-api/aos_api/aip_eval_subject_persisted_reader.py`：要求调用者在 `aos_runtime`、精确租户 GUC、repeatable read/serializable 事务中传入已经从 Owner 获取的封套和两份证书/Receipt。先读同租户 EvalRun：状态 succeeded，suite/target/judge、合同/subject/stage/policy/cutoff 与封套一致；再读 subject-review root、独立身份、不可变 Receipt 与撤销快照。比较行内容及 canonical hash，并调用原 `verify_subject_pair`。拒绝缺行、跨租户、不同用途、漂移、未来落盘或撤销；数据库异常统一封闭。函数不发证、不创建 Run/Report、不调用 Provider、不返回运行许可。
2. 新增 `services/aos-api/tests/aip/test_aip_eval_subject_persisted_reader_pg.py`：仅用标准临时 `aos_test_*_ti4_test` PostgreSQL，测试专用真实 Ed25519 签名；RED 后正向结构读取，逐个缺失/跨租户/撤销/上下文与行漂移、旧 eval-execution root 混用、错误角色/隔离级别失败。临时 seed 仅测代码，不算真实业务证明。
3. 专项与相邻回归后写 `subject-persisted-reader-verification-20261001.md`，精确提交。D-waves 与 AOS/Prime 记忆记录本波以及下一波 Owner/Writer/Report/Stage 缺口。

## 退出与风险

退出判据：隔离 PG 的正反证通过、旧 v1 测试不回退、`git diff --check` 干净；不改原 reader 或迁移。未来仍需原生成与安装来源、合法 EvalRun 创建 Owner、受限 writer、Report/Stage 消费链。任何来源缺失只阻断该实例，不扩大成整个 Goal `blocked`。
