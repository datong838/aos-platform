# E17-s3o-w-ao-b45｜事务绑定 readiness 第一施工点

## 方案/代码一致性

- 先复习 231-3/BIND-1 §5 与 b44 伪 evaluate RED，再写 b45 文件级方案。新增 `AipBindingReadinessService.for_transaction(conn)` 显式将现有 Postgres dependency authority、Model store/resolver 绑定调用方连接；`nullcontext` 不拥有连接、不提交。默认服务构造与历史 preview/evaluate 行为不改，也没有让普通发行账号取得表写权。
- disposable 全迁移 PG 中，先在一个事务插入唯一 test-only published CapabilityRevision。默认服务通过另一连接读不到，返回 `CAPABILITY_REVISION_UNAVAILABLE`；新入口经调用方连接读到，原因码消失但因其他依赖缺失仍 `blocked`；随后默认服务依然读不到，证明未暗中提交。测试末尾显式 rollback，不留新行。
- 本切片只解决连接可见性基础，**不**证明当前签名安装、撤销锁、任意依赖完整重算或直接 DML 防伪。b34/b37/b44 strict xfail 均保留，不接 active/run，也不把本波称为 E17 正式门 GREEN。

## 可复核命令

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob45_transaction_readiness_pg.py` | 实现前 exit1，`AttributeError: AipBindingReadinessService.for_transaction`；测试为真实 disposable PG。 |
| 同目录运行 `tests/aip/test_e17_s3owaob45_transaction_readiness_pg.py tests/aip/test_aip_binding_readiness_service.py tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py -k 'not downgrade'` | 实现后 exit0，22 passed、4 xfailed、7 warnings。 |
| 再追加 `test_e17_s3ol_capability_issuer_pg.py`、`test_e17_s3owaob12_tool_receipt_identity_pg.py`、`test_aip6_003_exact_instance.py`、`test_aip6_capability_run_handoff.py` 的七文件相邻回归 | exit0，35 passed、1 deselected、4 xfailed、7 warnings。 |
| `python3 -m compileall -q aos_api/aip_binding_readiness_service.py tests/aip/test_e17_s3owaob45_transaction_readiness_pg.py`、`git diff --check` | 均 exit0。 |
| `uv run ruff check ...` | exit2：本地环境缺少 Ruff 可执行文件；未把静态 lint 说成通过。 |

## 后续受限命令门

1. 在 disposable 全克隆用非 owner 独立账号先拒绝直接 Binding/Receipt UPDATE/INSERT、无 EXECUTE、跨租户/错版；保持 b44 伪 evaluate RED。不能仅因同连接就放行。
2. 为最终事务绑定 exact signed source 行锁/Registry撤销、依赖 Reader 当前计算、Binding CAS 与唯一 Receipt，并验证撤销竞争和任一步失败全回滚。若 SQL 函数无法完整执行 Python 聚合，先冻结不可伪造证明协议与权限分工，不用 GUC/历史快照替代。
3. 正式当前卷仍 `a0v_135` 只读，唯一136迁移及切换另波；正式 issuer/Reader/OIDC/Owner、active 安装、八配置/六 Binding/首链未齐，Host/worker/Provider关闭。Goal active、不 push。
