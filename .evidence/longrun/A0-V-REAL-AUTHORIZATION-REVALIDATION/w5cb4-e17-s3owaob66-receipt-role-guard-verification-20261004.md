# b66 verification：隔离 Receipt 身份 guard 合同

- Task `A0V-W5CB4-E17-S3OWAOB66-20261004`；先读 231-3/BIND-1、b63 plan、原 `aip6_002` 共享 Receipt、b22 同事务版本配对原型与 b46 受限 SECURITY DEFINER 命令。
- 文件级方案见同目录 `w5cb4-e17-s3owaob66-receipt-operation-guard-plan-20261004.md`。本波仅在 disposable PG 测试内部创建并 finally 删除 `BEFORE INSERT` guard：evaluate Receipt 必须在 evaluator definer 身份下插入。普通 lifecycle issuer 直接伪 evaluate 被 SQLSTATE42501 拒绝；同 issuer 原 create/Receipt 正向 `1 passed`，伪 Receipt count0。没有真实迁移或业务服务更改。
- 相邻 `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings --show-capture=no tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py tests/aip/test_e17_s3owaob46_restricted_evaluate_command_pg.py`：exit0，`8 passed/4 strict xfailed`。b22 的 deferred 配对与 b46 的仅 EXECUTE/同事务回滚原型保持现状。
- 原 b65 无 guard 的共享 Receipt 伪造 strict xfail 仍存在；本波 guard 只是 isolated 原型，尚未把 b22 配对和 b46 受限命令整合为唯一136，也未证明 evaluator definer、八类依赖、当前 signed Installation/Registry 锁的正式正向。不可标记当前实例授权完成或首链通过。
