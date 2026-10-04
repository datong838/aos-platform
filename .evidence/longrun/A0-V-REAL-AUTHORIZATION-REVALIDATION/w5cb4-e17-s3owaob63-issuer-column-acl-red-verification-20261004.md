# b63｜可信 available 合同与生命周期发行角色列级权限 RED

## 本波实际范围

- 复习 231-3/BIND-1 和 b22/b44/b45/b46/b49/b50/b62b 后，将签名来源、八依赖、Installation/Registry 锁、Binding CAS/Receipt 及身份拆分写入 b63 文件级方案。当前 `evaluate()` 在写事务外通过独立 Reader 预计算；Router 中 `capability_lifecycle` 发行登录必须持 Binding 表级 UPDATE。二者不能当作可信 available 最终事务。
- 仅在 `aos_test_*_ti4_test` 全迁移 disposable PG 增两个测试：一个证明普通 issuer 只获生命周期列 UPDATE 后无法直接改 readiness；一个 strict xfail 要求现有 lifecycle preflight 接受这组窄授权。生产代码、迁移、当前真库、API/Web/Host均未改。

## 验证命令和结果

| 命令 | 结果 |
| --- | --- |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q -rx --tb=short --disable-warnings tests/aip/test_e17_s3oo_capability_reader_pg.py -k 'column_grants or omit_readiness_column_write_grants'`（`services/aos-api`） | exit0，`1 passed/1 xfailed`；前者数据库拒绝 readiness UPDATE，后者身份预检仍拒窄授权。 |
| 相同 xfail 用 `--runxfail` | exit1，`RegistryIssuerConnectionBlocked: REGISTRY_ISSUER_DATABASE_IDENTITY_REQUIRED`，断在 `aip_registry_issuer_connection.py` preflight，不是测试库或口令故障。 |
| 两个相邻文件 `test_e17_s3oo_capability_reader_pg.py`、`test_e17_s3ol_capability_issuer_pg.py` | exit0，`16 passed/1 xfailed`。 |
| `python3 -m py_compile` 新增测试文件、`git diff --check` | exit0。 |

## 结论与下波

- PostgreSQL 列级授权可以收回普通 issuer 的 readiness 直写；当前 preflight 仍以表级 UPDATE 为前提。b63 是前置合同与 RED，不是可信 available 实现或当前实例放通。
- b64 应先最小改 `aip_registry_issuer_connection.py` 的 capability_lifecycle 身份预检，严格允许状态/健康/观察/版本/更新时间五列 UPDATE，拒绝 readiness/依赖/时间窗等其余列与表级 UPDATE；与 create/status 原路径、Receipt operation guard 及负租户回归。`evaluate` 在普通 issuer 下应失败关闭，正式受限 evaluator/唯一136另波联合正向。
- 当前库 a0v_135 只读，正式凭证/角色/八配置/六 Binding/自然首链仍缺；Host/worker/Provider关闭，不读商城源/旧 Run、不手工 run_definition、不碰230 L0、不 push。
