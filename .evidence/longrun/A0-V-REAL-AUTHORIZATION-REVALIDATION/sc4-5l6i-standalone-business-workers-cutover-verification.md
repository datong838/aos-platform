# SC4-5l6i 独立业务 Worker 与当前代次切换验证

日期：2026-09-15
结果：`STANDALONE_BUSINESS_WORKERS_CURRENT_GENERATION_GREEN`
代码提交：`6362ec09`、`545af3b0`、`a43a851d`
方案提交：`91e18f43`、`586423d2`、`9f4fc9c3`

## 实现与测试

- `scripts/a0v_ecommerce_runtime_host.py` 现在用同一个 runtime control plane 和 stop event 启动 lifecycle Host、ProductEvent Worker、AnalysisDataRequirement Worker。任一 Worker 构造失败时不宣告 ACTIVE；运行中意外退出时整体失败关闭。
- `scripts/a0v_ecommerce_current_reinstall.py` 增加 released-owner settlement 与 D 的 exact 生命周期路由。D 只能继承已释放并通过正式 disable Receipt 收敛的 C；未释放资源、未决 operation、canary写入或错误目标状态均拒绝。
- 专用测试库 `127.0.0.1:18432/postgres` 串行执行 73 项相关测试全部通过，覆盖独立 Host、两个业务 Worker、生产 runtime 装配和当前重装控制器。重启后默认 5433 不可用时，首次测试只在 pytest 会话建库阶段失败，未执行被测逻辑；使用既定专用测试库后通过。

## 真实切换

切换前 C 为 `044c2743-9700-4e84-a6c1-98670c94f005@5`，generation `09d2a19a-d85a-4c81-981c-87c1600944ea`，ready/enabled/unfenced，三个资源未释放。快照为仓外 `observe-before-host-code-cutover.json`。

旧 Host PID 37395 收到 SIGINT 后正常退出，三个 OCI 容器消失。主库随 Host cleanup 原子读回 C binding rev5/epoch4、disabled/fenced、desired=enabled、observed=unknown，三个资源均 released 且 observedRelease=true，canary=0。新 Host PID 49671 启动并写出：

- outcome=`RUNTIME_HOST_ACTIVE`
- businessWorkers=`product-event, analysis-data-requirement`
- positiveTenant=`org-org/dev-project`
- tenantCount=1，canaryTenantCount=0

对 C 发出的唯一 settlement disable operation `246a6a65-8863-40dd-a137-b6abe1533883` 由新 Host 消费成功；C 收敛为 binding rev7/epoch5、disabled/fenced、desired=disabled、observed=unknown，原资源保持 confirmed released。

D 通过正式 create、runtime-apply、runtime-verify、configure、enable 全链完成：

- installation=`e39ed226-97e7-4271-b1e0-fb485f7e90a6@5`
- generation=`04e71cc0-fff3-48bd-b357-1518ddd504a4`
- binding rev4/epoch3，ready/enabled/unfenced，desired=enabled
- configuration=`e92b9856-b530-4a2b-b28a-5101d36ac0a7@1`
- configuration hash=`sha256:5a279ff92b4b584c7a0f38a0b5d16debd3e9c5e673b3716ab9734806e05c216e`
- apply=`29a2abf3-49bd-474a-9a38-8d32149c1371`、verify=`849027a1-f07e-4581-a1f8-f9eba216b8fe`、configure=`1ef38ef4-4c30-40b1-8762-18edcf56ae5e`、enable=`420d6b01-9de9-44fd-95c7-2d0bc79ccf53`，均 succeeded
- 三个新 OCI 资源未释放并由当前 Host 持有；Docker中仅有这三个资源容器与主数据库
- AOS API `127.0.0.1:18181/v1/health` 返回 200/`status=ok`；5173 与 8434 前端均返回 200
- `dev-org/dev-project` installation count始终为0

## 边界与下一步

本结果证明代码重启后能通过新代次恢复当前包，并让自然链两个业务 Worker常驻；它不证明真实商城批次、Case/Run或经营建议已经产生。下一步只以 D 的 exact installation/generation/configuration 建立 P02 SourceSelection、RuntimeControl、ScheduleBinding并执行一次新鲜的栖月汇只读商品批次；C 不再作为当前业务引用。
