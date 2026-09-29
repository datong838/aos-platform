# W5CB4 BG-00ab｜持久 Eval authority 只读消费验证

## 文件与方案对照

- 方案：`w5cb4-bg00ab-persisted-eval-authority-reader-plan-20260929.md`。新增生产文件 `services/aos-api/aos_api/aip_eval_persisted_authority_reader.py`，新增隔离测试 `services/aos-api/tests/aip/test_aip_eval_persisted_authority_reader.py`；未加迁移、路由、配置开关或正式 authority 行。
- reader 对调用者单一 repeatable-read/serializable 事务核 runtime role 与精确租户 GUC；SELECT 四张表中的 issuer、identity、Target/Judge 两 Receipt 与截止点前撤销，校验 DB 列和签名声明一致，再交已有 `verify_execution_pair` 做独立双签名与精确 claim 验证。reader 本身仅 SELECT，不创建或批准签发来源。
- 测试使用 `colima-aos-a0v-test-only` 的 `aos_bg00z_acl_20260929@a0v_113`，仅在 `org-org/dev-project` 回滚事务内注入 test-only 密钥/行；`dev-org` 只以 GUC 做 RLS 负向读取。测试后四张表均 0 行。

## RED、修复、回归

- 最初机制测试 9 passed。复审发现纯签名时间与持久建档时间之间有漏口：未来建档的 Judge Receipt 可被早于建档时刻的核验接受。新增 `future_receipt` 负例后运行结果 `11 passed, 1 failed`，失败为 `DID NOT RAISE EvalExecutionRejected`，不是环境错误。
- 最小修复：issuer/identity 的 `created_at` 不得晚于已签 Receipt 的 `occurred_at`，Receipt 的 `created_at` 不得晚于 `evaluated_at`。复跑专项与相邻纯签名/ACL/对象 reader：`31 passed, 2 skipped`，退出 0；skip 为要求其他隔离环境的既有测试。`compileall -q` 与 `git diff --check` 退出 0。`ruff` 在该 venv 不存在（退出 127），不把它记为通过。
- 正反覆盖：空 root、缺 identity、缺双 Receipt、跨租户、identity/root 撤销、DB claim 漂移、issuer 过期、错误 DB role、未来建档和双签名正向。只证明隔离持久读取机制，不是正式 G2 Eval 或业务链通过。
- 当前权威库只读 `aos_current_preview_20260927@a0v_113` 四表均 0；`curl http://127.0.0.1:8080/v1/health` 与 `http://127.0.0.1:8434/aip/skill-publish` 均 HTTP 200，18181 无监听。曾误探测 `/health` 为 404，正确路由为 `/v1/health`；该 404 不代表 API 故障。

## 未完成与下波

当前正式 issuer/Owner/G2 内容与批准、真实 S3、同事务执行写 Receipt 和 Report/Gate 消费均缺；reader 尚未接到生产路由/Host，当前运行实例仍失败封闭。下一波 BG-00ac 先定位现有 Eval Run/Report/Gate 的精确事务边界，写最小持久消费方案与 RED；无合法正式 authority 时只推进隔离代码，不启动 Host、不手工 Run、不碰商城源/旧 12 Run。后续任何新表迁移需保留 ACL 克隆核验；自然首链、卸载重装、八工作台及发布判断仍未完成。
