# SC4-5l6j Niushop 1.23 E 代安装验证

日期：2026-09-15  
代码基线：`823229fd`  
范围：六步中的第 5/6 步；D→E 可恢复重装与运行宿主切换。

## 结论

电脑重启后，旧 D Host 已停止且三个 D 资源均有正式 released 事实。控制器没有把进程消失当成禁用成功，而是使用原 D installation/generation/binding revision 发出唯一 `settle-d` Receipt，并由加载 Niushop 1.23 签名根的新 Host 消费。D disable operation 最终 succeeded，binding 收敛为 revision 7、epoch 5、disabled/fenced、desired disabled。

E 随后以 D exact head 为直接前驱创建，完整通过 approved → applied → verified active → staged → configured → enabled。最终 E 是唯一 enabled/unfenced 的 current 代，三个 OCI 成员持续运行，Host 与 product-event、analysis-data-requirement 两个业务 Worker 同进程存活，canary 始终为零。

## D 正式收口

- D installation：`e39ed226-97e7-4271-b1e0-fb485f7e90a6@5`
- D generation：`04e71cc0-fff3-48bd-b357-1518ddd504a4`
- disable operation：`e4d7e094-2eb2-44b2-8744-65359de10e9c`，最终 `succeeded/succeeded`
- 最终 binding：revision 7、epoch 5、enabled=false、fenced=true、desired=disabled、observed=unknown
- 三个 D 资源全部 `cleanup_state=released` 且 `observed_release=true`
- 命令证据：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260915/state/current-ecommerce-package/install/settle-d-command.json`
- 命令 SHA-256：`c5761719e10e6e6187cc421629b6d0e407673482295e5eb83945f26158697988`

## E 生命周期

- E installation：`1c08edfb-ec0d-4abb-a411-7b6ec0d6066a@5`
- E generation：`ebaa620a-8831-4c2a-b971-788383f352f8`
- composition：`d3284b9f-9eab-4133-a79e-ccc4dbda2cab`
- lock：`sha256:f52df338f30b9f7d21fe31ec3ff1fc1a1c108c7c9e4cab3e3ea583ca31ccaa51`
- resolved：core 1.3、Niushop 1.23、growth 1.8、operations-base 1.2
- configuration：`18efcd3e-b0dc-4621-a349-4041341f5339@1`，hash `sha256:72e03bbd4e4a3f39111359e541079c57d80c4d409ba3a29bda881458da7951b6`
- 最终 binding：revision 4、epoch 3、enabled=true、fenced=false、desired=enabled、observed=ready
- lifecycle operations：
  - apply `7aa91e9e-eea5-4506-be67-a0162e824d5f` succeeded
  - verify `f273b89f-6556-46ad-9126-215e259ed71c` succeeded
  - configure `6fb0fcfe-7e22-4f46-8114-4dd79835fade` succeeded
  - enable `4fcaaf67-6b04-409e-bc39-eff15515d57d` succeeded
- E 三个资源为未释放的当前所有权资源；canary installation count=0。

## 运行宿主与 OCI

- Host status：`RUNTIME_HOST_ACTIVE`，pid 58194，tenantCount=1，positive tenant=`org-org/dev-project`，canaryTenantCount=0。
- 业务 Worker：`product-event`、`analysis-data-requirement`。
- 三个运行容器均为 running，网络均为 none：
  - core image/config `bc85b368fe05...`
  - Niushop 1.23 image/config `3cb783e202e7...`
  - growth image/config `271e36ba31ba...`

## 不可变证据

| 文件 | SHA-256 |
| --- | --- |
| `create-e-command.json` | `d8259a3a172f4b0ad8af0d473793c1ae81912e8fdf6ccfb61ea2ccf8d4fdb50d` |
| `prepare-e-command.json` | `d413b2a7fd5777bed213256af65ebb11715df171279bc10b4642bab1b7415e94` |
| `verify-e-command.json` | `2a9d9a4a619c739ca54aa0a9fe18088efa81cccfd95ba8531f29d92b50d2e12c` |
| `stage-e-command.json` | `ff6e811bf5f01bc4531a908f3d843aaab6a7e1e91e839f69f2017f7f4191cb8b` |
| `configure-e-command.json` | `0240c3f37beb78e493912623f552291c8fc08af82a6cea47815ba470c58e66b6` |
| `enable-e-command.json` | `128a7d2b4506758de18e25ef93bc5cc549f92557d8e7e4d539c83306e9e9e0de` |
| `final-readback.json` | `a950e961b6717f843614a17c4b0ac47532e178c42260ba9e4c761089ba5195c6` |

## 自动化验证与风险边界

重装控制器、构建、签名和候选合同定向测试共 `27 passed`，`git diff --check` 通过。重启前旧 Host 的终态文件记录 `HOST_RUNTIME_FAILED`，但数据库正式事实明确证明 D 三资源 released；本波没有覆盖旧终态文件，也没有重发旧命令。新 Host 使用独立状态文件，当前持续运行。

本步只证明安装、配置、禁入恢复和宿主所有权切换。P02 新鲜真实读取、Dataset、ProductEvent/Case 尚未执行，不能据此声称首链成功。

## 下一步

进入第 6/6 步：把 P02 current preflight 与业务控制器固定到 E create Receipt、Niushop 1.23 签名资产和新的私有状态目录；验证旧 D ref 被拒绝、E exact ref 可用。随后开启下一波，以一个新鲜 P02 批次验证 observation 版本真正消除同键冲突，并观察 Dataset → ProductEvent → Case/Run 自然触发。
