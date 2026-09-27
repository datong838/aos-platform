# W5CB4 E14：运行包旧入口精确拒绝与当前 Host 门验收（2026-09-28）

## 结论

本波完成**正式入口的错误语义和页面引导**，没有激活安装，也没有提交任何 runtime 操作。E13 已拒绝的通用 Apply 没有重发；当前唯一安装仍 approved/revision3/ETag3、active 空，runtime operation/binding/Host assignment 均 0。正式 `runtime-apply`→`runtime-verify` 仍待当前独立身份、Host 分配、资源和工作进程准入，不把页面按钮或测试当作运行结果。

## 九步证据

1. 复习产品 12、231/231-9 BG-00、231-3 的运行包隔离安装合同和 E13 验收 `2c8ae924`；前置计划 `66c5a437`，现场收窄 `3f1cdc17`。
2. 当前预览启动器明确 `AOS_EXTENSION_RUNTIME_HOST_ENABLED=0`，且当前卷 `extension_runtime_host_assignment=0`；运行包独立身份文件/Host/OCI 不可仅从历史角色名推定已就绪。因此本波不向无 Owner 队列提交 runtime 操作。文件清单收窄为 Registry typed error/revalidator/测试、前端错误策略与安装动作提示/测试。
3. 新增 409 `RUNTIME_OPERATION_REQUIRED`，只在旧通用安装 revalidator 读到所选 Registry 行的 `manifest.spec.runtime` 时产生；此分流本身**不证明**该包签名/发布有效，正式运行路径仍须重验。保留普通过期发布包 `REGISTRY_SNAPSHOT_STALE` 及纯内容 Apply/Verify 路径。前端把该**已知拒绝**归为 failure-closed，提示转到同页“运行实例”，不再错误建议“刷新后重试”；安装动作面板明示通用路径仅供纯内容包。
4. RED 为新错误类缺失的测试收集失败；GREEN：Registry 及 runtime 制品专项 29/29，新增纯内容反证 3/3，错误/相邻测试 18/18，HTTP 安装生命周期 1/1；`test_installation_baseline_pg.py` 在当前测试环境 42 项跳过，**未计为通过**。
5. 前端动作/错误专项 46/46，累计 307 文件 2690/2690；TypeScript `tsc --noEmit` 和 Vite build 通过。build 有既有大 chunk 告警，不作为本波阻断。
6. 用当天最新代码和**原命名卷**完整重启 DB/API/Web：PG 容器 `aos-a0v-recovery-pg` 挂载 `aos-a0v-recovery-pg-data`，库 schema `a0v_109`；8080 `/v1/health=ok`、`/v1/ready=ready`，8434 页面 HTTP200，18181 关闭，Host/worker0。浏览器 `/apollo/assets` 重新读取后唯一安装仍 approved、revision/ETag3/active 无、事件3；面板可见“通用 Apply/Verify 仅适用于纯内容包；运行包请使用下方运行实例”及运行实例 `not_prepared`/无代次。未点击任何写按钮。初次页面在重启竞态下显示读取失败，手动只读重试恢复；不能称为自然业务验收。
7. 代码/方案复审：后端围栏仍在，`RuntimeOperationRequiredError` 只改变可区分错误码；无权限扩张、无执行副作用、无商城源读取、无旧 Run 重发。**剩余缺口**：安装详情读模型尚未权威标记包类型，通用 Apply 按旧状态机仍显示按钮；本波仅提供提示和服务端拒绝，不能声称产品入口已完全防误点。E15 优先补权威包类型投影及前端真正禁入，同时建设当前隔离 Host 的合法身份/配置路径，避免过度停留在文字提示。
8. 本 verification 落盘，E14 仅按上述范围完成；当前业务首链、安装激活、正式来源/管道/Selection 均未达成。
9. 精确提交代码与本文件，更新 AOS/Prime 上下文后自动进入 E15。每日继续用最新 m1+当前权威卷全面重启并读回，不依赖定时唤醒；保留所有卷/备份，不 push，230 L0 与旧 12 Run 继续冻结。
