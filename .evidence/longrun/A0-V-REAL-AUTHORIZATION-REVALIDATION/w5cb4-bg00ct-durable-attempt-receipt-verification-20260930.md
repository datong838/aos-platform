# W5CB4 BG00ct｜持久 attempt Receipt 原语验证

- 基线：m1 `acd0fd2a`、AOS-000949；任务 Receipt `W5CB4-BG00CT-20260930`；文件级方案 `w5cb4-bg00ct-durable-attempt-receipt-plan-20260930.md`。
- RED：`AOS_TEST_USE_SHARED_DATABASE=1 services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/aip/test_aip_network_issuer_attempt.py` 退出1，缺模块 4 failed。
- GREEN/邻接：attempt/service/auth/reconcile/contracts 五文件，退出0，`32 passed, 2 skipped`；compileall、diff check 退出0。跳过的是需显式隔离 PG proof 的查询项，不计作通过。
- 逻辑复审：只在 caller 已验签 principal 与 Command tenant 精确一致时受理；以 tenant+idempotency key 哈希命名，私有 issuer UID 0700 目录内 `O_EXCL|O_NOFOLLOW` 创建0600 Receipt，写入 exact proposal/key/hash/subject 后 fsync 文件与目录才返回。重放/并发仅一方可获首次权；冲突、空/损坏/宽权限文件与目录均拒绝。Receipt 不含 JWT 或决策正文，无重试/清理/网络/数据库副作用。
- 方案边界：本波只产出未来独立签发进程的 at-most-once 前置原语；尚未把它与 BG00cs Inquiry、BG00cn `decide` 接成私有进程，未验证正式 OS 用户或持久目录备份/恢复。当前库、现网 API、Host/worker/Provider 未变，Approval Event/首链均未完成。
- 下一波：BG00cu 在隔离克隆组合外部身份→reserve→单次 decide→精确 Event 读回，注入崩溃/超时；无正式 IdP/OS/HBA 时当前实例继续禁入。
