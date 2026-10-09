# Source finalize 后签发认证到期的实际提交观察

基线 37a2cefe / AOS-001627。Goal 经官方接口回读 active；未私改存储或另建 Goal。本 Task 仅诊断，产品代码没有变化。

r3 两布局 2 PASS / 75.70 秒 / 7 既有 warnings：原真实 Source、SERIAL/SCRAM issuer 和真实 20 秒 OIDC 签名 JWT，finalize 时有效，数据库时钟越过 JWT exp 后实际 caller COMMIT 均成功，此时 Source 的 valid_until 仍在未来。

- shared：finalize 02:47:01.390857 UTC；JWT exp 02:47:20；COMMIT 前 02:47:20.105707；Source valid_until 02:51:57.744446。
- distinct：finalize 02:47:33.447974；JWT exp 02:47:52；COMMIT 前 02:47:52.105994；Source valid_until 02:52:28.321416。

独立只读核验两个原 xid committed、Source native C 签名/hash/finalized/原 xid PID session 历史出处、临时三个入口移除、issuer/occupation NOLOGIN、31 旧资源及原产品文件 hash 不变。

失败保留：r1 未加载原 conftest，2 setup ERROR，未进入业务；r2 字段误用 expires_at，且新节点未进入逐节点隔离名单，1 FAILED / 1 ERROR；独立核其发行五表全零，注册 epoch 留存不删除。r3 仅改真实字段 valid_until 和显式调用原建库/缓存恢复实现。审计首轮联表字段歧义修为精确 ON；初始版本保留。收口文档首次写入因 stdin 编码失败未生成，本文件补齐，未重跑业务或重发 COMMIT。

结论仅证明 finalize 与 caller COMMIT 之间签发 JWT 到期的实际行为。没有跨越 Source 自身有效期，不能判定违反最终提交时间合同，更不能宣称提交时效保证、整体 Source 交付或正式首链完成。原 Source/profile/legacy 三 Task 仍 ACTIVE；独立督导 daemon 故障为局部待恢复。

下一登记安全步骤：调查 Source valid_until、签名 permit、审批时间门的真实 caller COMMIT 依赖，区分 statement-end 与实际 COMMIT；未取得真实 Source 有效期跨越提交证据前不修改语义。无当前库写入、重启、Provider/Host/worker、其他分支、push 或 Goal 状态修改。
