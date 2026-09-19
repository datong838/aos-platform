# AY 过期 enable 结算与未激活退休方案

## 冻结权威

AY installation `81df994f-23ce-4448-ac46-366aaee63924` 为 active@etag5，generation
`a1069f60-46f5-41a8-bd18-61ed677eb3bd` 的 Binding 固定为 rev3/epoch2、disabled/fenced、
desired disabled、observed unknown；配置 `ce24590a-479e-4a5e-94ab-01d138e0675c` rev1/hash
`sha256:579a652e471f626f08e25f80f19b4e9f77b91531a456dac87ef2f2220e1cff89`。三项 Runtime
资源均为 released/observed release。

原 enable operation `24a85b28-f00d-43cf-ba5d-28f064c74f6a` 是唯一未终态 operation，仍为
accepted/accepted 且 deadline 已过；唯一 Host 已停止。AY 从未完成 successor register，也没有 cutover、dispatch
绑定、occurrence 或 execution attempt。九路仍是 AX 退休后的 legacy rev125/group152；definition rev79 disabled。

## Rules 与实现范围

- 不恢复、不重发原 enable，不修改 deadline，不手写 operation/binding/outbox 终态。
- 复用既有 `RuntimeDisableService`：在同一事务内验证并取消精确过期 enable、创建独立 disable Receipt 和 fence；
  再由既有 `RuntimeDisableConsumer` 只领取该 disable 的 exact outbox 并完成 `disabled_committed`。
- 因 AY 从未 register/cutover，dispatch lifecycle 正确结果是零 fence/detach Receipt、九路 legacy 不变；不得伪造
  detach。正式退休使用既有 `configured_unactivated` uninstall authority，要求当前 disable 证据、配置、资源释放、
  零接入与零业务执行，输出不可变卸载 Receipt。
- 不启动 Runtime Host、Cron 或 snapshot worker；不读商城源数据；230 L0 挂起；`dev-org/dev-project` 仅零 canary。
- 文件仅新增 AY 窄执行器、专项测试、verification；不修改通用生产实现。

## 串行步骤与停止条件

1. `preflight`：精确核验上述 installation/binding/config/resources/过期 enable、legacy 路由、definition、12 个
   running Run 与 12 个 Dataset Receipt，以及 Store Receipt/`ecom_link`/projection/canary 均为零。
2. `request-disable`：冻结新幂等键与 rev3 target；调用正式 DisableService。只接受原 enable 变为 cancelled，独立
   disable 进入 fencing，Binding 变为 rev4/epoch3 draining/fenced；任何未知只读回查原 operationId。
3. `process-disable`：只领取独立 disable 的 exact outbox；完成后要求 disable succeeded、Binding rev5/epoch3
   disabled/unknown/fenced，并有 exact `disabled_committed`。九路 legacy 不变，dispatch lifecycle 为零。
4. `retire`：通过正常 Installation Owner 以 active@etag5 提交 configured-unactivated uninstall；要求 AY
   `uninstalled@6`、active revision 为空，回执明确引用上述 disable operation/configRef，重复同键只可 replay。
5. `audit`：再次核验原 enable cancelled、disable/uninstall 终态、资源释放、零 Host/attempt/业务副作用、九路
   legacy rev125/group152 与 definition rev79 disabled。
6. 专项测试、编译、`git diff --check` 通过；verification 落盘并精确提交后，才创建 AZ direct successor。

任一步 Receipt、revision、hash、零副作用边界不符即停止并冻结；不得换 key、不得启动 Host、不得提前创建 AZ。
