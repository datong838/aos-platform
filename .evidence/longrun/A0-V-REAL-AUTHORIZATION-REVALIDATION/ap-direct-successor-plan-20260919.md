# AP direct successor 与冻结十二源恢复方案

## 目标与边界

AO 已通过正式 Runtime Owner 退休。AP 作为 AO 的唯一 direct successor，必须消费 detach Receipt `c98d7a33-2653-42a8-86f1-05f26c09217e` / `sha256:b4e2969a445b0459dd0e43376d600ab87a515374774e3434d31a28eb014c29f9`，从 legacy route group revision125 开始注册。AP 身份、generation、configuration 与安装 lock 必须由正式 lifecycle 结果产生，禁止预造。

本波继续复用 snapshot group `c5ff1926-45b0-56de-b6b3-07d5b7d053a1` 的十二个 Run、dataset receipt、relationship 与 link command。禁止回读商城十二源，禁止人工 `run_definition`，禁止重发未知结果。

## 文件级清单

1. `scripts/a0v_ap_replacement_recovery.py`
   - 只接受 AO exact detached binding revision8 / epoch4、3/3 resource released、route revision98 / group125、disable operation 与 detach Receipt；
   - 执行 `preflight → create-ap → prepare-ap → verify-ap → stage-ap → configure-ap → enable-ap → observe`；
   - 每一步使用独立幂等键和 0600 私有回执。
2. `scripts/a0v_ap_successor_business.py`
   - 只消费上述 AO detach Receipt；
   - AP ready 后从 group125 注册九条 extension route，并只接受正式 registration Receipt。
3. `scripts/a0v_ap_successor_cutover.py`
   - 固定 AP registration Receipt，完成 binding/route/current-permission/canary 对账。
4. `scripts/a0v_ap_saved_snapshot_recovery.py`
   - 从 AO revision60 disabled definition 转移到 AP，续租冻结 recovery，配置十二 controls 后启用；
   - 不读取源数据，不直接执行 definition。
5. 对应 `services/aos-api/tests/extension_runtime/test_a0v_ap_*.py`
   - 覆盖 exact predecessor Receipt、revision、幂等键、无 `run_definition`、零源读取与 tenant canary。

## 执行顺序、停止规则与完成条件

先完成 AP replacement 的方案、实现、专项测试与只读 preflight；再逐阶段执行正式 lifecycle，每一步读回后才进入下一步。随后依次完成 successor registration、cutover 和 saved snapshot transfer/renew/enable。任一身份、Receipt、route revision、pending operation、canary、Store 零提交边界或十二源冻结事实漂移即停止写动作并只读对账。

本波完成条件是 AP 安装启用、九路由正式注册、冻结十二源 definition/recovery 转移并自然产生唯一 recoverable Store attempt。测试绿、AP 安装成功或 route 注册成功都不单独代表经营参谋自然首链完成。
