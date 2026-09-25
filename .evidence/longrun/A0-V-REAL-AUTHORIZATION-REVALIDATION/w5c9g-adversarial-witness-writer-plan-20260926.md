# W5c9g｜恶意自洽输入对 `a0v_098` 写门的隔离行为

## 上位边界

承接 W5c9f `m1@4a10692a`/AOS-000694：一次性 PG 可提交原 ingress envelopeHash 准确、rowCount/rowsHash 错误却格式/manifestHash 自洽的 immutable 原组，sidecar 仍 0。`a0v_098` 目的只是保存原 claim/input/member 的 canonical 文本，operator 未授应用；不能因函数 `INSERTED` 推断行级真实性、ACK 或 closure。真实库没有迁 096/097/098、全机 Fleet/Owner 仍无授权。

## 文件级最小清单

- 仅扩展 `services/aos-api/tests/extension_runtime/test_a0v_w5c9f_self_consistent_fixture_pg.py`：复用同一一次性 PG 夹具，按 W5c8q 精确建独立 NOLOGIN/NOBYPASSRLS caller、显式 SET ROLE operator、org/project GUC、REPEATABLE READ；用 `reconstruct_witness` 生成与原 hash 一致的 canonical 参数调用函数一次。无效 caller/scope 或漏身份仍拒绝；调用结果与 sidecar 原字节/哈希精确回读，测试结束 REVOKE/DROP 临时 caller、数据库残留 0。
- 首先 RED 测明函数实际返回；若 `INSERTED`，仅标 `CANONICAL_ONLY_UNTRUSTED_SEMANTICS` 风险边界，不改生产函数为假“校验完整”。审计全仓 sidecar 读取点仍只 migration/test，未接运行时 ACK；若发现应用路径，则 STOP 独立修复。
- `a0v_098` migration、真实角色、HTTP/PG 服务、原十二 Run 均不改；只隔离测试，不读商城源。测试中不执行任何真实业务 effect。

## 九步

1. 复习 231、W5c8q/r、W5c9f 与原组 no-authority。
2. 本方案先提交。
3. 静态调用点与隔离身份/fixture 前检；测试 RED。
4. 最小增测试与必要的 fixture 重构，生产不改。
5. 专项 PG、相关累计与测试 DB/role 清理回读。
6. 复审 canonical 保存与 row semantics、ACK/closure 的权威分层。
7. 8080 业务浏览器离线，不填业务 GREEN。
8. audit/verification、m1、D-waves/AOS CAS/Prime。
9. 自动下一波：若 writer 可保存语义错误的合法原输入，设计下游**独立** row semantic proof/拒绝门，绝不以 sidecar 给真实 ACK；若 writer 拒绝，固定拒绝矩阵。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 run_definition、m1 单写不 push。
