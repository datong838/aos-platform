# a0v054 本地部署实证

基线 2895a811。部署器边界测试 6 passed；本次实际执行 test_event_control_dispatch_lifecycle_pg.py 为 14 passed，不能引用其他波次组合测试数量替代本次结果。

第一次在线恢复验证 540 表指纹一致，但主库 runtime event/outbox/operation/resource lease 四表变化，apply 在意图创建前拒绝，版本仍 a0v053。保留该备份和隔离库。受控 Host PID58194 正常 SIGTERM 并输出 STOPPED；静止窗口第二次备份恢复到 aos_event_dispatch_quiesced_20260916_test，540 表一致。随后主库精确 a0v053→054，读回 EVENT_DISPATCH_LOCAL_SCHEMA_DEPLOYED，540 表指纹不变、收据数0、强制RLS、runtime不可写、maintainer不可改删、PUBLIC不可执行受控函数。

私有证据 .aos-recovery-20260916/state/event-dispatch-deployment-quiesced/{prepare,apply-intent,apply,host-maintenance-intent,host-restart}.json。Host 按原参数恢复 PID82238，状态 ACTIVE、租户1、canary0，8434首页HTTP200。

注意：维护窗口 Host 停止后 E 的绑定变为 revision7/epoch4、enabled=false/fenced=true，desired仍enabled/observed unknown，三资源已释放。尚未主动执行 E 的正式 disable/detach；F不存在。不能宣称 E 仍可接单或已正式退役。下一波使用已有 settle-e 对释放后受保护状态收口，核对 exact ar2_017 detach Receipt，再创建F。该状态已记录，不通过改表解除禁入。

波次6/6：迁移完成，下一波 E→F 正式退役与安装。真实首链、八工作台和连续观察未完成；不 push、230 L0挂起。
