# W5c9b｜原十二 Run 与 authority 只读对账

## 上位边界

承接 W5c9a `m1@b239b719`/AOS-000689：仅一个恢复 PG，18181 纯 HTTP Host=0/Cron=false/snapshot=false/migration disabled，8080 仍离线。旧 A0-V generation 的 attempt 曾以 `PermissionError`/`HealthObservationStale` 正式终结，但原十二 Run 在早前证据中仍 running；rev4 disabled 不等于退休。不得把 AT 2026-09-19 rev70/72 方案误套到当前原 Run；W5c8a–g 的 receipt/源组 resolver 只在隔离 PG 证明且未接真实业务。商城源数据不读。

## 本波只读文件级清单

- 只新增 plan、audit、verification；先提交本 plan，不改代码/配置/服务/数据库。
- 复核 18181 PID/租约、唯一 PG、8080 job 缺席；读取原 generation/attempt 的**精确 ID**及原十二 Run ID，仅从已提交证据/只读 authority 获取，不从含凭据的配置输出。身份/ID 无法唯一确定则 STOP，不泛查数据库。
- 评估 `a0v_w5c5b_real_closure_preflight.py`、W5c4t/W5c5e/g 只读边界；仅允许强制 `transaction_read_only=on` 的 SELECT/HTTP GET，不触发带 `FOR SHARE/UPDATE` 的旧 resolver。只输出原十二 Run 的聚合 status 计数、Receipt 数和固定 no-authority flags，不输出源 payload、商城行、DSN/Env/凭据。
- 若现有脚本有副作用或身份不明，本波只完成静态/现有证据核对并给下一波缺口，不临时编造 SQL 或越过权限。绝不迁移真实库、改变 rev4、运行定义、开启自然 worker、回填或 ACK。

## 九步

1. 复习 A0-V、W5c5/W5c8 与现行冻结状态。
2. 本方案先提交。
3. 新鲜服务/租约/PG/身份只读前检。
4. 最小只读 authority/原 Run/Receipt 对账，未知即 STOP。
5. 专项只读结果与原十二 ID/状态一致性复核；无代码测试不冒充。
6. 累计回归只引用 W5c9a 15 tests，不冒充真实 closure。
7. 8080 业务浏览器离线；18181 `/docs` 不替代业务验收。
8. audit/verification、m1、D-waves/AOS CAS/Prime 更新。
9. 自动下一波：基于精确差异，先方案补只读 reader 或设计正式退休/direct successor；未知结果不能重发。

230 L0 挂起、dev-org 零 canary、m1 单写不 push。
