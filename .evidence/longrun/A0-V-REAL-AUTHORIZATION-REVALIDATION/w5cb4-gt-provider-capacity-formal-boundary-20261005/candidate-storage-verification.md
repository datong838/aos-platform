# S12 原候选存储读取验收

基线 ac0399db4e594dfee11bd702f2e21ebe970bfeba；原 formal-boundary Task 同 owner 续 Lease 至2026-10-06 20:00+08，无新增写者。

## 实现与范围

CAPACITY_CANDIDATE_ROW_SQL 接入原 Source guard._candidate。固定原 public 表及 pg_catalog builtins，正向双租户与 ID/revision/kind、actual/stored/expected hash、原 mode/两 IS FALSE、精确三键、JSON string kind/maker 与原行和原 Source maker 一致。保留原 Python 全部检查、模型重解析、内部 tenant 门和 Provider/Evidence/withdrawal/currentness 锁序。没有新 schema、function、GRANT、迁移、正式发行入口或真实库操作。

## 本次证据

- candidate-storage-red.log：4 failed/10.12s，缺新SQL常量 ImportError 为所需实现尚不存在的 RED；不是业务拒绝反例成功。
- candidate-storage-green.log：4 passed/10.00s。真实隔离私有SCRAM两种候选正向及错 hash/tenant/id/revision/kind/maker 六类查询负向；每类15项 TEMP 单字段故障，JSON故障重算stored/expected hash检验独立结构拒绝。TEMP最终rollback。
- candidate-storage-adjacent.log：448 passed、7既有warnings、196.91s，进程exit0。覆盖原 request/action/source_action/formal_boundary/publication/source_contracts 六模块。
- candidate-storage-review.md：现有督导受邀独立只读复审，无新的重大问题；后继向完整发行入口闭合。git diff --check通过。

## 限制与接续

S12存储部分已接入真实原消费者，完整SQL typed candidate尚未完成；S13账户/basis/request组合与S14–S19依赖锁/可信签名/窗口需按等价方案组合到完整入口。待决真正COMMIT时TTL合同不由本门解决。供应商事实、共享账本/Intent、Model/Route、b90八facts/COMMIT/API及自然首链尚无本次通过证据，原Task/Goal不收口。
