# CQ 正式退休与 CR direct successor 方案（2026-09-21）

## 1. 当前权威

- HEAD `56ea986e`；CQ installation `fff0b0d3-bf8f-44b0-b1b7-6a2972daeb80` /
  generation `ae8a1005-99fb-48c5-9dfe-8f76590bc0c8` 已 blocked retirement。
- Binding rev11/epoch6 disabled/fenced/desired disabled/observed unknown；九路 legacy
  rev254/group281；三资源 released；Host=0、18181=0。
- 唯一 disable `36c3d6ca-db24-4553-a0ec-8748006b3dd8`；fence
  `839b0c44-68a0-467f-b8ae-0fe1d8e8a3bf` /
  `sha256:03b41b959cd7f80f12f204cdab85c7cbefa41965a25263b3d1ecef7043511f63`；detach
  `2d8a382b-90f1-46c3-9100-c2310a949914` /
  `sha256:3b618e589557064bf049dd344fa9bdc345236d22a38ec2c1558d2a968d08b432`。
- definition rev193 disabled；CQ attempt=0。12 members、12 running Run、12 Dataset
  Receipt；Store Receipt=0、`ecom_link`=0、projection pending=0、canary=0。
- current BudgetPolicy/RuntimePolicy 为 rev11。CR 必须在全新 installation/configuration
  中引用 current authority，使后续 saved-snapshot prepare 仍落在 Binding rev6/epoch3。
- 不读取商城源数据，不调用 `run_definition`。本波仍属 BG-00 生命周期实证。

## 2. 串行步骤 1-6

1. **plan/preflight**：冻结上述 exact CQ detach 权威；核对 m1 单写者、Host=0、18181=0。
2. **创建 CR**：仅以 CQ detach Receipt 为 predecessor 创建新 installation/generation。
3. **lifecycle**：串行 prepare、verify、stage、configure、enable；prepare accepted 后只
   启动唯一外置 Host 自然领取。第二 Host=0。
4. **注册与九路 cutover**：唯一幂等键注册 CR；串行 approve、prepare、pause、commit、
   validate、resume，目标九路 rev255/group282。
5. **唯一 Host 与健康观察**：第二 Host=0、18181=0、snapshot worker=0；只读
   repeatable-read 观察 lease renewal、binding ready、route 一致与 attempt=0。health
   baseline 必须是当时 live renewals，目标 +12。
6. **verification/commit**：读回 12/12 与全部零副作用，落 verification、测试、精确提交；
   自动进入 CR saved-snapshot recovery。

## 3. 停止条件

任一 identity/Receipt/hash/revision/attempt/Run/route 漂移，出现第二 Host/worker、商城源
读取、负租户写、业务副作用、未知提交边界或手工执行时立即 fail closed。未知结果不得重发
或更换幂等键；不 push、不动其他分支，230 L0 继续挂起；非人工决策工程问题由当前唯一开发
最小修复并继续。
