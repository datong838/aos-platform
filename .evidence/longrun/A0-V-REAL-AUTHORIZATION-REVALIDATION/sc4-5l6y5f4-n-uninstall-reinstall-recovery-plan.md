# Y5f4-N J 卸载重装与业务路由恢复方案

日期：2026-09-16

基线：m1 `d27f6d44`

## 实态与决策

J installation `d6531562-e388-4206-a3ba-a89aaddc255c` 已完成正式 runtime disable 和九路 detach。binding 为 revision 11 / epoch 6 / disabled / fenced / unknown；三份 resource lease 均为 released，所有 runtime operation 均为终态，九路为 legacy fenced revision 20 / group revision 35，event-control 不存在，canary 为零。

正式 enable 要求当前进程持有 verified `PreparedJob` 且资源 lease 未释放。J 的资源已释放，禁止复活旧 container、伪造 owner 或直接修改 binding。恢复采用已存在的 replacement installation 流程：先以 J 的不可变 current-installation ref 创建 K approved，随后正式卸载 J，再准备/验证/配置/启用 K，并以 J detach Receipt 注册和切换九路。

## 固定执行顺序

1. preflight 精确验证 a0v072、J head/lock、binding、全部 operation 终态、三资源 released、detach Receipt、九路 legacy fenced、零 inflight、零 canary。
2. `create-k`：保留新鲜主库备份，以 J 的 installationId/revision/lockHash/overlayRevision 为 `current_installation_ref`，从现有已签名 event-complete bundle root 创建独立 K approved installation。创建结果和 intent 不可变；未知结果只读检查，不重发。
3. `uninstall-j`：只在 K 仍为 approved、J 无任何 dispatch 挂载、资源已确认释放、detach 两 Receipt 完整时，通过 InstallationService/RuntimeUninstallGuard 正式卸载 J；读回 state=uninstalled、activeRevision=null。
4. `prepare-k` 与 `verify-k`：只由独立 Runtime Host 的正式 preparation owner 消费；验证 signed bundle、三资源、健康、租户和当前 replacement 权威。K verify 后应为 active、disabled/fenced/ready。
5. `stage/configure/enable-k`：复用当前四源配置授权和固定执行器；配置引用使用当前 K 自己的不可变配置历史。enable 后 K 为 ready/unfenced，schedule 与 event-control 保持禁用。
6. 以 J detach Receipt `15f04808-68e3-481f-9e20-9c6cf43a49a8` 作为 predecessor authority，注册 K 九路，再走 prepare/pause/commit/validate/resume 原子切换。最终九路必须指向 K generation/epoch，group revision 单调递增，无业务 Run 自动启动。

## 准备中断恢复分支

真实执行中，旧 Host 在 K 的 `runtime-apply` 成功后退出，资源清理器已把 K 的三份 lease 正式置为 released；随后提交的 verify 因不存在 PreparedJob 只能保持 accepted。禁止复活 K 的容器或直接修改 operation。固定恢复分支如下：

1. 保持九路 legacy fenced、零 inflight、零 canary；启动并持续观察唯一新 Host。
2. 等待 K verify 到期后，通过正式 `RuntimeLifecycleService.reset_preparation` 将失主验证终态化并把 K 从 applied 回退到 approved；未知结果期间不重发 verify。
3. 以“当前不存在 active baseline”为前提创建无 predecessor 的 L approved installation；只有 L 获批后，才通过 RuntimeUninstallGuard 正式卸载 applied/released K。
4. L 的 prepare/verify 必须由当前存活 Host 连续消费；任一 Host 退出都再次停止，不降级为数据库直写。
5. 后续 stage/configure/enable 与九路注册、切换目标由 K 改为 L；J detach Receipt 仍是业务路由恢复的来源权威。

该分支是卸载重装和失败恢复能力的真实验证结果，不把中断的 K 计作成功安装。

## 停止条件

- 任一 head、lock、Receipt/hash、group revision、资源释放、inflight 或 canary 漂移，写入前停止。
- 任一 state-changing phase 有 intent 而无确定结果，只读查 Receipt/operation，不重发。
- K 未 approved 前不卸载 J；J 未正式卸载前不验证 K；若 K 准备中断，L 未 approved 前不卸载 K；L 未 ready/unfenced 前不注册或切换。
- 不启动 schedule、event-control、商城上游写入、外部发布或业务自然 Run。

## 文件范围

- `scripts/a0v_j_uninstall_reinstall_recovery.py`
- 对应执行器单元测试
- 本计划与分阶段 JSON/Markdown 证据

不修改领域运行时写模型；优先复用已验证的 InstallationService、Runtime Host、配置 owner、successor registration 和 cutover owner。
