# SC4-5L6Z-S｜重启后干净安装恢复与九路由切流结果

日期：2026-09-17。范围：`org-org/dev-project`；负租户：`dev-org/dev-project`。
本结果承接 Q 重启后资源释放及正式退役，只恢复安装运行权威与内部九路由；未修改商城源数据，
未生成经营 Run，未执行外部发布、触达或 230 L0 动作。

## 1. 失败关闭与恢复路径

- Q `9c49b383-e04d-41b4-8276-8b8bc6db49a8` 已经通过正式 disable consumer 完成
  fence/detach，并正式卸载为 `uninstalled@6`；三项资源均 `released`。
- 第一替代实例 R `adf3c333-60e9-47c3-81bc-a35ba4067b77` 在 Q 卸载后执行 verify，
  被当前性守卫拒绝。Host 停止并释放三项资源，verify 保持 accepted，未形成 binding。
- 等待原 verify 租约自然过期后，通过正式 `reset_preparation` 将 R 从 `applied@4` 回退为
  `approved@5`；创建 clean S 后，再正式卸载 R 为 `uninstalled@6`。没有直接 DML、没有重发
  结果未知的 verify、没有恢复旧 owner。

## 2. S 安装与运行终态

- installation：`77b8e5c2-db96-4d55-a808-1b62e00163d2 active@5`；
- generation：`e621100a-baea-440f-9075-ae8a5290845a`；
- binding：`revision6 / epoch3 / enabled / ready / unfenced`；
- 四项 lifecycle operation（apply、verify、configure、enable）全部 succeeded；
- 三项资源均由当前唯一 Host 持有，`cleanup_state=pending / observed_release=false`；
- Runtime Host PID 35613 为 ACTIVE，live target 仅 S，canary target 为 0。

## 3. successor 登记与切流

- 前驱权威：Q detach Receipt
  `2bcb4ff2-9da1-4bc8-a3b3-7ed98e18eb4d`，content hash
  `sha256:cc974be8c9e22afeea41d3dd665c4f4b92c50899e245d2df0869d78658d11f5f`；
- 登记 Receipt：`1588b754-4e6d-41d0-994d-596437a447b1`；
- cutover operation：`eea1d47d-6bc3-5972-b1f2-5a30430ce7bd`；
- approve、prepare、pause、commit、validate、resume 全阶段完成，observed status 为 resumed，
  rollback 为空；
- 九条 `ECOMMERCE_GROWTH_OPERATIONS` 路由全部为
  `extension / S / epoch3 / unfenced / routeRevision33 / groupRevision60`；
- running execution=0，claimed/unknown occurrence=0，负租户 installation=0。

机器可读终态见 `sc4-5l6z-s-successor-cutover-final-state.json`。只读验证结果：
`S_SUCCESSOR_NINE_ROUTE_CUTOVER_GREEN`。

## 4. 代码、测试与一致性

- 新增 `scripts/a0v_r_replacement_install.py`：冻结 Q→R 中断→S 恢复顺序；
- 新增 `scripts/a0v_s_successor_business.py`：只接受 exact S、Q detach Receipt、group59；
- 新增 `scripts/a0v_s_successor_cutover.py`：独立 operation/idempotency namespace；
- 新增 `scripts/a0v_s_successor_cutover_verify.py`：只读核对安装、旧实例、路由、Host、在途和 canary；
- `py_compile` 与 `git diff --check` 通过；
- preparation reset、未知结果不重发、successor registration 与 cutover contract 专项共
  `55 passed`。首次测试漏加 `PYTHONPATH=scripts` 导致 7 个模块导入失败，修正测试入口后
  同一组全部通过；不是产品逻辑失败。

## 5. 下一波

将 baseline 控制执行器的目标从退役 Q 改为 S；按 S 当前 installation/generation/epoch
重新签发来源控制和一次性调度控制，创建独立 baseline Case/Policy，并由 Host 自然生成
occurrence 与首个真实 BusinessInvestigationRun。不得复用 Q 的旧安装绑定或旧来源控制凭据。
