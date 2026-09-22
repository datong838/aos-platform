# DM claimed-null-container 恢复方案（2026-09-22）

## 上位方案复习

- DM successor 3/6：`5103c27a…` approved@etag3；prepare `ec7a706f…`
  `needs_attention/preparing/RESOURCE_CLEANUP_UNCERTAIN` rev9；deadline 已过。
- 三资源：2×released（含 1×`resource_intent_cancelled` + 1×created-then-released）；
  唯一 uncertain `4d407243…`：**`create_claimed_at` 有值、`container_id` 为 null、无
  `resource_created` 事件**（Host 在 create 认领后、写 container 前死亡）。
- 现有 `ExpiredResourceRecovery`：`remove_owned` 对 absent 返回 false；随后
  `confirm_absent` **强制 64 位 container ID** → `TypeError` 被吞成 `uncertain`。
  Host 会永久空转，liveTargets=[]。浏览器 N/A。

## 本波文件级清单

| 步 | 路径 |
|---|---|
| 1 | 本方案 |
| 2 | `services/aos-api/aos_api/extension_runtime/oci_driver.py` |
| 3 | `services/aos-api/aos_api/extension_runtime/resource_recovery.py` |
| 4 | `services/aos-api/tests/extension_runtime/test_oci_driver.py` |
| 5 | `services/aos-api/tests/extension_runtime/test_resource_recovery_pg.py` |
| 6 | `scripts/a0v_dm_uncertain_cleanup_recovery.py` + replacement-dm 证据 |

## 不变量（最小改动）

1. **双标识路径不变**：journal 已有 `container_id` 时，仍必须 name+container 双
   `confirm_absent`；任一存在保持 uncertain。
2. **仅当 journal `container_id is None`（create 从未被观察）**：租约已过期后，
   先 `remove_owned(..., expected_container_id=None)`；若 false，再
   `confirm_name_absent(name, owner)`（只读 inspect name）。name 明确 `No such`
   → 记 released；name 仍存在或非 No-such 错误 → 保持 uncertain。
3. 禁止直接 UPDATE lease；禁止伪造 container_id；禁止在租约仍 live 时结算。
4. 三资源 released 后，正式 `settle_failed_preparation`（phase=`preparing`）将 apply
   标 failed；再以**新 idempotency key** 重发 prepare（旧
   `a0v-current-ecommerce-dm-prepare-20260915` 不可复用），继续 verify→enable。
5. 恢复期间唯一 Host：先 SIGTERM 现 Host，恢复结算后再启，避免 advisory 锁竞态。

## 串行退出

1. 专项测试 GREEN（oci + recovery PG）
2. DM uncertain 资源 released + settle_failed_preparation
3. 新 prepare 被唯一 Host 消费至 applied，再 verify/stage/configure/enable
4. 不改 w2；不 push；字母环无 UI → 浏览器 N/A

## 下一波任务（本能力 GREEN 且 DM enable 后）

DM successor **4/6**：注册 + cutover **318/345**。
