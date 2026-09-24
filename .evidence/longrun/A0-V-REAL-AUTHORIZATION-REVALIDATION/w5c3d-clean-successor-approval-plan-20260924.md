# W5c3d 干净 predecessor-free 继任者仅批准方案（2026-09-24）

## 依据与边界

W5c3c `b86930fe`：DS 与失败安装均正式 uninstalled，失败 apply/三资源历史终态不可重用；唯一 Host PID 15014 空载，九路 legacy/fenced、12 schedule off、业务计数不变。原 `create_approved_first_installation` 支持 `current_installation_ref=None`；原 `load_active_baseline_in_transaction` 明确拒绝引用无 activeRevision 的已卸载安装。历史 T/U、M/N、Q 等恢复使用 predecessor-free 创建，故本波只新建干净 approved 安装，不把卸载对象冒充 active baseline。

## 串行步骤

1. 只读检查两旧安装 uninstalled/activeRevision null、失败 operation 和三个租约仍终态、无新 installation 业务尝试；Host 唯一 ACTIVE 空载；九路 9/9 legacy/fenced、12 schedule disabled、canary0；签名四包和信任根精确匹配 W5c1 版本；全新 Command 前缀未占用。
2. 新增 `scripts/a0v_w5c3d_clean_successor.py` 及定向测试，0600 intent/result、全新幂等前缀 `a0v-w5c3d-clean-successor-20260924-v1`，调用原安装器一次，显式 `current_installation_ref=None`。任一中间 Command 边界未知，停止，按精确前缀只读对账，禁止重发。
3. 独立读回 composition lock 的 predecessor null、四包版本、8 模块、唯一 installation approved/etag3、四个原生 Command、无 operation/binding/resource/attempt，旧两安装仍 uninstalled，Host 空载、九路/调度/canary/业务计数不变；verification 后提交 m1。
4. 下一波再以唯一 Host、全新单次 prepare/verify intent 开始，50 秒只读采样至正式终态；此波绝不 prepare、verify、enable、切路由或调度，不读商城源。

## 停止条件

任一旧安装/资源/Host/预算/签名/路由/调度漂移，Command 已有同前缀，原 Owner 拒绝或提交边界未知，立刻冻结并先只读对账。
