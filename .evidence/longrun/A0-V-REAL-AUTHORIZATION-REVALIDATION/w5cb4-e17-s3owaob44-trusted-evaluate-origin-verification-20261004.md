# E17-s3o-w-ao-b44｜可信 evaluate 来源 RED

## 结论

依据 b44 文件级方案，仅在既有 disposable 全迁移 PG 测试加一个 strict xfail 分支：随机非 owner、test-only issuer 直接把任意 `b`×64 写作 dependency snapshot hash，同时更新评估时间、版本、readiness 并在同一事务插入 evaluate Receipt。新增分支要求数据库拒绝，但当前 test-only 双向守卫接受，故稳定 xfail；原分支仍通过。这个证据只证来源缺口，不能把当前实例或首链报 GREEN。

`AipCapabilityBindingService.evaluate` 先由 readiness Reader 在其独立连接计算，再在 issuer 连接写 Binding/Receipt；`update(active)` 的重算也通过独立 Reader 连接。仅在 Python 层补一次读回无法阻止有表 UPDATE 权限的 issuer 绕过服务或在撤销竞态中写过期结果。正式方案需把 exact 签名来源锁、当前依赖计算或不可伪造证明、Binding CAS、唯一 Receipt 放在受限最终事务；Reader/issuer 不得直接具有可伪造的通用 DML。b41 锁函数与 b25 operation guard 需合并成唯一后续迁移合同，当前 `a0v_135` 不改。

## 可复核证据

| 检查 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings tests/aip/test_e17_s3owaob22_capability_receipt_identity_pg.py -k 'not downgrade'` (`services/aos-api`) | exit 0；1 passed、2 xfailed。新增 xfail 为合法外形但无可信计算的 evaluate；另一个为原共享 Receipt 缺门。 |
| 同目录，追加 `test_e17_s3ol_capability_issuer_pg.py`、`test_e17_s3owaob12_tool_receipt_identity_pg.py`、`test_aip6_003_exact_instance.py`、`test_aip6_capability_run_handoff.py`、`test_aip_binding_readiness_service.py` | exit 0；34 passed、1 deselected、4 xfailed。 |
| `git diff --check` | exit 0。 |

## 风险与下一步

正式凭据、当前 active 安装、八配置、六 Binding、Host Owner/OIDC 尚未齐；本波不启 Host/worker/Provider，不写真实库，不碰商城源/旧 Run/230 L0。下一波 b45 在独立完整克隆先设计/验证受限最终事务命令的 EXECUTE/直接 DML 负门、撤销/换代并发、exact source/依赖计算、失败回滚和 Receipt 唯一性，再决定唯一 `a0v_136` 迁移。配置和产品绑定安全项可以并行推进，不把此 RED 当全 Goal blocked。
