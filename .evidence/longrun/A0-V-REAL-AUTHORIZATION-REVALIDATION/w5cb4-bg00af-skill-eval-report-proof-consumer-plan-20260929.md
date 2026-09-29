# W5CB4 BG-00af｜Skill Eval Report 全 case proof 只读消费者方案

## 上位与权限发现

228 G2.2/231、BG-00ac/ad/ae 要求正式 G2 内容、双签名 Receipt 与可消费 Report/Gate。当前 a0v114 sidecar 可绑定同 tenant/run/case 的 Report 和 Target/Judge Receipt/claim hash，但尚无消费代码。BG-00z 当前库四张签发/identity/Receipt 表对 `aos_runtime` **仅 SELECT**，而新 sidecar 为 SELECT/INSERT；在没有合法正式 issuer/Owner/审批和专属 writer 权威前，直接授运行角色 INSERT 或绕过 ACL 均违反既有安全门。故本波把原定写入/消费拆成可独立完成的**只读 Report proof consumer**，写入权威单独 BG-00ag 复审；生产 Skill runner guard 不解除。

## 文件级最小实现

1. 新增 `services/aos-api/aos_api/aip_eval_report_proof_reader.py`：接受调用方同一 repeatable-read 已绑定租户连接、不可变 `EvalReportRevision`、每 case 独立来源的预期 input hash 与已呈交的 Target/Judge 双证书/Receipt，返回全 case 验证结果。逐项从当前同一 snapshot 回读 Report 完整 row/hash、sidecar exact case 集合，再调用 BG-00ab 持久 reader 验证 root/identity/revocation/双签名和 Receipt；结果与 Report 每 case 的 actual/expected/pass/detail、sidecar ID/hash/时间一一相等。缺一个、多一个、重复 case、错 hash/租户/时间、Report 漂移均 `EvalExecutionRejected`。只 SELECT，不注册路由或 Gate、不伪造 authority。
2. 新增 `services/aos-api/tests/aip/test_aip_eval_report_proof_reader.py`：test-only `aos_bg00ad_schema_v2_20260929@a0v114` 的回滚事务，先 RED 缺 sidecar/错 claim；正向用独立 test-only 密钥与已签 Receipt，精确插入 Report/sidecar；跨租户 canary 只读。专项及相邻累计复验，四 authority/sidecar 表回滚后空。

本波通过只证明隔离读取机制。正式 G2 producer/issuer/Owner、真实 S3、同事务可信写入和 ReleaseGate 当前消费仍缺；当前空表实例必拒。BG-00ag 先审 writer 权限来源和同事务执行所有者，禁止放宽 a0v113 的四表 ACL；若需要新迁移，当前库切换另立备份/克隆/零执行窗口。
