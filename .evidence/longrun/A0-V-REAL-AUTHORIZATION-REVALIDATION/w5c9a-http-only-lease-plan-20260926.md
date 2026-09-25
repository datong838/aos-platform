# W5c9a｜纯 HTTP 18181 新租约与零执行启动门

## 上位方案与新发现

承接 AT 保存快照恢复方案及 W5c8z `m1@2ba47c64`/AOS-000688：唯一恢复 PG Up，8080/18181 free，旧 8080 job 缺席。`scripts/a0v_product_controlled_api.py` 委托 `a0v_controlled_api.py` 的 `require_leases()`；现唯一匹配 `A0V-W5C4P-SNAPSHOT-WORKER-20260924` lease 已于 2026-09-25 12:00 CST 到期，旧默认 task 不存在。**不得绕过、复活或静默延长旧租约**，不能直接 `check/serve`。新租约仅授本机 18181 进程所有权，不授权商城源、Worker、迁移或原 attempt。

## 文件级最小清单

- 正式 `scripts/memory/memory-receipt task-start` 以新 task ID `A0V-W5C9A-HTTP-ONLY-20260926`、owner=m1、唯一 scope=`local-process/aos-api-18181`、短有效期、实时 authority expected-revision 创建专用租约；旧任务不更新。先验证 18181 free、PG 唯一、8080 job 缺席、无相同 task/重叠 owner。
- `scripts/a0v_controlled_api.py`：只在现有两 task 白名单外新增该**精确** task ID，且如 W5c4p 一样强制 scope 精确、ACTIVE、m1、未过期；所有旧默认行为不变。`AOS_CONTROLLED_API_LEASE_TASK` 必须显式设置为新 task，不能接受任意字符串。
- `services/aos-api/tests/test_a0v_controlled_api.py`：新增新租约正例、缺失/过期/错误 scope/owner/任意 ID 拒绝；锁定四个零执行旗标。先 RED，再最小代码 GREEN。
- `scripts/a0v_product_controlled_api.py`、生产 API/DB/Worker 不改。运行前 `check` 的输出只读取 outcome、四 flags、sourceCalls/runsCreated，绝不打印 DSN/Env；若 preflight 因私有 identity/lease 失败，不启动 `serve`，冻结查因。

## 串行九步

1. 复习 AT/AS、W5c8z、现行控制器与 lease 治理；确认真 PG-only 状态。
2. 本方案先提交。
3. 新鲜只读租约/端口/PG/8080 前检；正式 CAS task-start 新租约；RED 定向测试。
4. 最小白名单代码改动，不影响旧 task/服务。
5. 专项 GREEN 和相关累计回归；配置/租约再读回。
6. 纯 HTTP `check` 成功且 flag/readiness 无效应时，单次 `serve`；运行态确认 Cron=false、snapshot=false、Host=0、migration disabled、18181 唯一监听、8080 job absent、Docker 仍唯一 PG。任何未知停止推进，不重发。
7. 8080 业务浏览器仍不可验收；如 18181 可用，仅检无业务副作用的健康/契约端点，不把此当业务 GREEN；方案/代码一致性复审。
8. verification 落盘、m1 提交、D-waves/AOS CAS/Prime。
9. 自动下一波：纯 HTTP 若真绿色，仅只读原 authority/Run/Receipt 对账；不运行定义，不开启自然 worker。若未绿，先修具体门，不能跳过。

230 L0 挂起、dev-org 零 canary、不读商城源、不 push。未知提交边界一律冻结/只读对账。
