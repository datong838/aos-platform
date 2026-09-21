# CQ 配置接续受阻实例正式退休验证（2026-09-21）

## 结果

`CQ_BLOCKED_RETIREMENT_GREEN`。CQ installation `fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80` /
generation `ae8a1005-99fb-48c5-9dfe-8f76590bc0c8` 已正式退休。唯一 disable operation
`36c3d6ca-db24-4553-a0ec-8748006b3dd8`；请求 receipt 非 replay。既有 Host PID 8784 完成
fence/detach 后，执行器先读回正式终态并冻结 `resendDisable=false`，没有再次领取或提交。
随后 SIGTERM 8784，第二 Host=0。

## 停止原因与配置治理证据

- 首次 saved-snapshot `prepare` 在任何结果/业务写入前被已到期 BudgetPolicy rev10 拒绝，CQ
  attempt 保持 0；
- 三个公共合成文本探针 3/3 通过，恰好三次 Provider 调用；planHash
  `57bdebd9dec1405691d1d1f331cf49a24efcbd1a1c3a933dc86f05ba7b8423bf` 正式续期 BudgetPolicy/
  RuntimePolicy rev11；
- CQ 同 configuration family 新建 rev2，hash
  `sha256:4fd728d8652c1be02b8300865283839c1cb4d86f0f2b6e120685a45c82fb632a`；configure
  `3bc3460e-1b76-4aae-96f9-d23204b86a57`、enable `1f330063-94a2-44a2-96a8-b7a858d67480`
  均正式 succeeded，Binding 到 rev9/epoch5；
- 重试 `prepare` 被 `current J binding differs` 拒绝（合同要求 rev6/epoch3）；
- 唯一旧 configuration refresh receipt 仍属 J activation。未执行 refresh、未直接改
  dispatch、未增加数据库迁移。

## 退休终态

- Binding rev11/epoch6：disabled、fenced、desired disabled、observed unknown；
- 九路回 legacy rev254/group281，三资源全部 released；
- definition rev193 disabled，CQ execution attempt 数量仍为 0；
- fence Receipt `839b0c44-68a0-467f-b8ae-0fe1d8e8a3bf`，hash
  `sha256:03b41b959cd7f80f12f204cdab85c7cbefa41965a25263b3d1ecef7043511f63`；
- detach Receipt `2d8a382b-90f1-46c3-9100-c2310a949914`，hash
  `sha256:3b618e589557064bf049dd344fa9bdc345236d22a38ec2c1558d2a968d08b432`；
- 十二 Run 仍 running，十二 Dataset Receipt 保留；Store Receipt、links、projection pending
  与 `dev-org/dev-project` canary 全部为零；
- 18181 已关闭且端口无监听；未调用 `run_definition`，未读取商城源数据。

## 验证

- CQ configuration successor 与 CQ blocked retirement 专项：`3 passed`；
- 方案与执行一致：旧 refresh 历史没有被跨 activation 复用，未知结果没有重发，唯一 disable
  经正式 Owner/Host 完成，快照与业务零副作用边界未变化。

## 下一波

从本次 CQ exact detach Receipt 创建 CR direct successor。CR 必须基于 current policy 和新
configuration 完成安装、配置、登记、切换与长续租观察；definition 保持 rev193 disabled。
完成 CR verification 并提交后，才允许重新规划 saved-snapshot recovery；230 L0 继续挂起，
不 push。
