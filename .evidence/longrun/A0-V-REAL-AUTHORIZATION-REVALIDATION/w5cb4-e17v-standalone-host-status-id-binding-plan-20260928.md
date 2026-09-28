# W5CB4 E17-v｜独立 Host 状态精确 ID 绑定文件级方案

## 已读合同

E17-l 的 `CURRENT_SIGNED_HOST_READONLY_PREFLIGHT_GREEN` 只有在当前签名库、独立三身份、实际 directory role/role OID、精确 `org-org/dev-project` assignment、八配置候选都通过时才包含 `hostId`。E17-u 现场 Host identity/assignment 仍为 0。独立 `a0v_ecommerce_runtime_host.py` 的公开运行状态却写死 2026-09-12 Host ID；`main` 的 `FORMAL_OWNER_AUTHORITY_UNPROVEN` 禁入当前保持。

## 文件级最小改动

1. `services/aos-api/tests/extension_runtime/test_a0v_ecommerce_runtime_host.py`：先 RED，要求 `_current_preflight` 返回且严格验证 E17-l 报告中的精确 `hostId`、scope、GREEN outcome；缺失/空白/非精确报告固定拒绝。内部 `_serve` 测试需显式传预检所得 Host ID，运行状态不得出现旧常量。保留 CLI 预检 GREEN 仍 Owner 禁入用例。
2. `scripts/a0v_ecommerce_runtime_host.py`：`_current_preflight` 仅把经 E17-l 返回的精确 `hostId` 传给调用方；`_serve` 需要显式可信 host_id 参数并写进状态，不再写旧常量。`main` 即使取得 ID 仍固定 `FORMAL_OWNER_AUTHORITY_UNPROVEN`，不进入 `_serve`。不增加新配置捷径或手工 Host ID 参数。
3. 专项和邻接回归、当前无正式凭据负向。当前库只读，Host/worker/Provider 不启动，不读商城源或旧 Run。

## 下波

当前无正式 Host identity/assignment 或操作批准，不能做真实正向 Host。下一波需沿 231-3 查正式供给与 Owner/Approval/Receipt 写入产品链；只有真实权威逐项齐备才另波评估解除硬门。`browser-pilot` 截图仍待恢复。
