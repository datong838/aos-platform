# b64｜Capability 生命周期 issuer 精确列级预检

## 改动和上位方案一致性

- 按 b64 文件级方案，`aip_registry_issuer_connection.py` 从 PG 目录枚举全部非删除 Binding 列，并逐列读取 session_user 的 UPDATE 权限。`capability_lifecycle` 只接受 `health/observed_at/status/updated_at/version` 五列；普通 `capability` 不接受任何 UPDATE 列；表级 UPDATE、额外 readiness/依赖/未来新增列的 UPDATE 均拒绝。原 tenant、身份、RLS、Receipt 和跨域检查保留。
- 旧测试中广授权发行身份可运行 `evaluate` 的路径已改为在窄授权下失败关闭：Reader 仍独立只读计算，但 Binding version1、evaluate Receipt0；`active` 拒绝，合法 `provisioning→revoked` 状态更新和对应 Receipt 仍正向。这个修补只收窄发行角色，**没有**可信 evaluator/正式 available 正向；不能以 blocked 计算或页面可点当首链。
- 生产代码未新增迁移或真实库 GRANT。当前 `aos_current_preview_20260927@a0v_135` 只读，现无正式私有 issuer 配置，Host/worker/Provider继续关闭。

## 验证

| 命令 | 结果 |
| --- | --- |
| b63 原 strict xfail 单跑（去标记前） | `XPASS(strict)` exit1，证明窄授权 preflight RED 被修复。 |
| b64 两用例单跑 | exit0，`2 passed`，窄授权通过且旧 evaluate 失败关闭。 |
| `AOS_DOTENV_DISABLED=1 uv run pytest -q --tb=short --disable-warnings --show-capture=no tests/aip/test_e17_s3oo_capability_reader_pg.py tests/aip/test_e17_s3ol_capability_issuer_pg.py tests/aip/test_aip_binding_api.py`（`services/aos-api`） | exit0，`27 passed/8 warnings`；包含表级 UPDATE、缺 version、额外 readiness 列、DELETE、旧 create/status、Reader 和 API 组合测试。 |
| `python3 -m py_compile` 两改动文件、`git diff --check` | exit0。 |

## 剩余风险与下一步

- 正式 issuer/DB ACL 迁移未落，当前卷不受此代码测试授权。共享 Receipt INSERT 仍需按 evaluate operation 严格配对，受限可信 evaluator 的 signed Installation/Registry 锁、八依赖最终事务计算、Binding CAS/唯一 Receipt及合法正向未完成；b62/b62b forged available RED 的**正式链路缺口未解除**。
- b65 应先让普通 issuer `evaluate` API 返回明确禁入（不在计算后才得到通用持久化异常），并隔离证明 evaluate Receipt 不能单独伪造；之后才设计专用受限命令/唯一136联合正向。正式凭证、当前卷新备份/全恢复/零执行窗口另门。
