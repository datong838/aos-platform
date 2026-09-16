# SC4-5L6Y5F4 V：L 已释放代到 M 新代受控重建方案

日期：2026-09-17

## 目标

当前 L 因租约过期已被安全栅栏，三资源均确认释放；binding 仍保留 `desired_state=enabled`。复核发现 Policy9 的正式事件 binding 仍为 enabled，且路由组仍含第十条 `ecommerce_growth_event_control`。常规控制 Host 和 event dispatch fence/shrink 都只接受 `enabled/ready` runtime，不能在已经安全栅栏的 released generation 上完成负向清理。本波先补一个严格限于 released generation 的退役恢复入口，再沿正式生命周期把 L 收敛为 disabled/detached，创建同签名版本的 M replacement，正式卸载 L，再让 M 依次完成 prepare、verify、stage、configure、enable。禁止复用 L generation、resource、container 或旧操作 Receipt。

## 固定顺序与门禁

1. preflight：L 必须 active@etag5、唯一旧 generation、binding `enabled=false/fenced=true/desired=enabled/observed=unknown`、三资源 released、旧操作 terminal、canary 0、在途执行和未决 occurrence 0；路由必须为同一 group revision 37 的九条业务路由加一条 event-control 路由；Policy9 binding 必须是 L/generation/epoch3/revision1。
2. disable-policy9：新增 released-only control service，只接受当前签名 control contract、当前租户控制者、exact Policy9 ref、L 当前安全栅栏、三资源 released、零在途和未决。它复用原 `ProductEventBindingControlStore` CAS 与原不可变 `EventPolicyControlReceipt`；只允许 disable，不提供 enable 或来源读取。
3. retire-event-route：在 a0v_074 数据库门禁中给原 event dispatch `fence`/`shrink` 增加 released-only 分支。仍使用原 strict request、独立 exact approval、签名 release qualification、两阶段 group CAS 和原不可变 Receipt；额外要求 Policy9 已 disabled、L 安全栅栏、三资源 released、零在途。fence 后检查 drain，再 shrink；任何 ready runtime 或其他退化状态都不能进入此分支。
4. settle-l：event-control 已移除且只剩九条业务路由后，复用 `RuntimeDisableService` 和当前 exact binding revision，写唯一幂等 Receipt；Host 通过原 disable consumer完成业务路由 fence/drain/detach。未知结果只读原 key，不换 key 重发。
5. create/uninstall：L 必须已 disabled/unknown、资源 released、操作 terminal、当前完整九路 detached；先留数据库备份，创建 approved M，再用正式 Installation uninstall Owner 卸载 L并保留 predecessor history。
6. M prepare/verify：L 已 uninstalled 后复用正式 lifecycle Owner。实际执行中 Runtime Host 未在电脑重启后持续运行；M 的 apply 已成功，verify 仅停在 accepted，三资源均由原清理路径确认 released，未形成 binding，也没有业务执行。该状态禁止直接 stage 或再次发送 verify。
7. M→N 恢复：等待 M 原 verify deadline 真实过期后，复用正式 `reset_preparation` Owner 将 M 从 applied@etag4 重置为 approved@etag5；精确要求唯一 apply succeeded、唯一 verify accepted+deadline-expired、零 binding、三 released resource、canary 0。随后先创建无 predecessor 的 approved N，正式卸载 M，再由已恢复且持有 singleton lock 的独立 Runtime Host 消费 N 的 prepare、verify。任何 M verify 被 Host 先行终结、资源不再 released 或状态不匹配都停止并重新判定，不能套用本恢复路径。
8. N stage/configure/enable：只有 N verify terminal green、三资源 live 且 binding ready 后继续正式 lifecycle；enable 成功后不恢复自然 schedule。下一波 W 登记 successor、完成九路 cutover、重载 Host 并确认唯一 N live target。Host 恢复使用现有三身份凭据、可信根和已签名 bundle，不创建或复制凭据；启动状态、PID、singleton lock 与数据库 live target 均落证据。

## 文件

- `scripts/a0v_m_reinstall_recovery.py`
- `services/aos-api/aos_api/ecommerce_released_event_control.py`
- `services/aos-api/alembic/versions/a0v_074_released_event_control_retirement.py`
- `services/aos-api/tests/extension_runtime/test_a0v_m_reinstall_recovery.py`
- `services/aos-api/tests/extension_runtime/test_ecommerce_released_event_control.py`
- `services/aos-api/tests/extension_runtime/test_released_event_control_retirement_pg.py`
- 本目录 V 方案、执行和最终证据。

## 停止条件

任一 current identity、revision、策略 ref、资源释放、路由 phase、canary、在途计数、独立 approval 或 Receipt 回读不匹配即停止；不以执行脚本手改业务状态、不复用旧 idempotency key、不启用业务 schedule。迁移只扩展现有安全函数的精确 released 分支，现有 ready 分支及全部正向执行不变。M 原 verify deadline 未过期前不 reset；Host singleton/三身份/可信根未确认前不创建 N。下一波 W 只在 N enabled/ready 且三资源 live 后登记 successor、完成九路 cutover、重载 Host 并确认唯一 N live target。
