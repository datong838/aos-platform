# AW 配置接续受阻实例正式退休验证

## 结果

AW installation `f94b9425-9bc4-4369-8ae3-138c50c9ab81`、generation
`a92f7bb2-3d90-4d88-9632-5fc9a70bd650` 已正式退休。唯一 disable operation 为
`0b77ae08-9c8c-4453-9f2b-709bddaca312`；请求 receipt 非 replay。既有 Host 完成 fence/detach 后，执行器
先读回正式终态并冻结 `resendDisable=false`，没有再次领取或提交。

## 停止原因与配置治理证据

- 首次 saved-snapshot `prepare` 在任何结果/业务写入前被已到期 BudgetPolicy rev8 拒绝，AW attempt 保持 0；
- 三个公共合成文本探针 3/3 通过，恰好三次 Provider 调用；随后策略正式续期，发布 runtimePolicy rev9；
- AW 同 configuration family 新建 rev2，hash
  `sha256:a7a6867754a7dee44b47461886a3afee380e867244dd2c6cdf235969593b3bec`；configure operation
  `051d9ec7-41f1-4e0b-b05d-4eb030360870`、enable operation
  `a76c83a9-3e4d-4612-bb2d-62e5dd410f41` 均正式 succeeded，Binding 到 rev9/epoch5；
- 只读复核证明唯一旧 configuration refresh receipt 属于不同 J activation。现有 Owner 与不可变触发器要求
  同 activation/installation/generation 连续链，故 AW refresh 无合法 sourceAuthorityRef。未执行 refresh、未直接改
  dispatch、未增加数据库迁移；按方案停止并转 retirement + direct successor。

## 退休终态

- Binding rev11/epoch6：disabled、fenced、desired disabled、observed unknown；
- 九路回 legacy rev122/group149，三资源全部 released；
- definition rev76 disabled，AW execution attempt 数量仍为 0；
- fence Receipt `47439302-5d24-41dc-84dd-20f33193ec8d`，hash
  `sha256:f50ee76cf398b8c441ce9a3d01a379434e20d0cb99f6ac439845ad41ebc1677e`；
- detach Receipt `0c50775b-62fe-4251-81f4-3c9a8709a90e`，hash
  `sha256:22b3fbf13e9fb92d3f7a4744a5f2787c9b0d3adf216727ed01439f1cb18d9226`；
- 十二 Run 仍 running，十二 Dataset Receipt 保留；Store Receipt、links、projection pending、running、
  unresolved、runtime pending 与 `dev-org/dev-project` canary 全部为零；
- 18181 纯 HTTP 服务已正常关闭且端口无监听；未调用 `run_definition`，未读取商城源数据。

## 验证

- AW/AS retirement、AW configuration successor、AW/AV saved snapshot、configuration refresh Owner 专项：
  `9 passed`；
- Python 编译与差异检查通过；
- 方案与执行一致：旧 refresh 历史没有被跨 activation 复用，未知结果没有重发，唯一 disable 经正式
  Owner/Host 完成，快照与业务零副作用边界未变化。

## 下一波

从本次 AW exact detach Receipt 创建 AX direct successor。AX 必须基于 current policy 和新 configuration 完成
安装、配置、登记、切换与长续租观察；definition 保持 rev76 disabled。完成 AX verification 并提交后，才允许重新
规划 saved-snapshot recovery；230 L0 继续挂起，不 push。
