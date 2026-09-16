# SC4-5L6Z-Q｜重启后 Q 运行所有权负向收敛结果

日期：2026-09-17。目标 installation：`9c49b383-e04d-41b4-8276-8b8bc6db49a8`；generation：`98aea676-ee71-4d42-a6c8-6634960efe5e`。

## 结果

- 起点确认 Q 仍为 active installation，但运行 binding 已因租约回收进入 `revision7 / epoch4 / fenced / observed=unknown`，三项资源均已释放。
- Policy12 的 event binding 经 released negative Owner 从 `revision1/enabled` 变为 `revision2/disabled`；没有调用商城源数据，没有补造事件。
- `ecommerce_growth_event_control` 经两次独立 exact ActionApprovalEvent 完成 fence 与 shrink；10 路缩为正式 9 路。
- 正式 disable operation `c4a48488-9088-4db9-b71e-7811ae7c3d8a` 经 consumer 完成，生命周期回执顺序为 `fence -> detach`。
- 最终九项入口均回到 legacy/fenced，group revision 59；Q runtime 为 `revision9 / epoch5 / disabled / fenced`。
- 全程 running execution=0、unresolved dispatch=0、Q occurrence=0、canary route=0、外部副作用=0。

## 验证

- `test_qyh_reboot_recovery_guard.py`、`test_ecommerce_released_event_control.py`、`test_event_control_dispatch_lifecycle_pg.py`：37 项通过。
- 私有逐阶段 intent/result 位于 `.aos-recovery-20260917/state/q-advisor-baseline/reboot-q-retirement/`，权限为 `0600`。
- Q 已不可执行但尚未卸载；下一步以 detach Receipt 为前驱创建干净 R，待 R 完成注册和 cutover 后再决定 Q 的正式卸载时点。
