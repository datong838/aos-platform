# BR 正式退休与 BS direct successor 安全停止验证（2026-09-20）

## 结论

`BS_DIRECT_SUCCESSOR_SAFE_STOPPED_AFTER_CUTOVER`。

BR 已正式退休，BS 已完成 lifecycle、注册和九路 cutover；但唯一 BS Runtime Host 在健康观察达标前因
`QueryCanceled` 失败退出。Owner 已将 BS binding 收敛为 rev7/epoch4 disabled/fenced，并将 apply
operation 标记为 `needs_attention / RESOURCE_CLEANUP_UNCERTAIN`：三项资源中2项 released、1项 uncertain。
因此本波严格按方案停止条件冻结，不原地重启 BS、不把 cutover 成功误报为 direct-successor GREEN。

## 1/6 plan/preflight

- 基线 HEAD `116ed18d`；BR installation `fddfa0b0-158c-4271-b1ea-dc4e1e36e293` / generation
  `981d7a2d-3bbe-4cc1-a8d9-c872be0147d3`，binding rev6/epoch3 enabled/ready，九路
  rev177/group204，唯一 Host PID 26889。
- 唯一 attempt `256207c9-4bc4-4c89-b00f-146f58012011` 为 failed rev8，definition rev127
  disabled、recovery41；12 members、12 running Run、12 Dataset Receipt与全部零副作用边界保持。
- BR 退休/BS successor专项39项通过；worker=0、18181=0，Host身份与status-file精确匹配。

## 2/6 BR 正式退休

- PID 26889收到SIGTERM后正常退出，status-file为 `RUNTIME_HOST_STOPPED`；Owner形成 binding
  rev7/epoch4 disabled/fenced/desired enabled，三资源 released。
- disable operation `91705b53-691b-4ebc-bab5-ba21945c9ec9`正式 succeeded；fence Receipt
  `d470630a-e0ea-4b23-80ad-3e9a728fcc44` / hash
  `sha256:5853837835bb545de2e066c26edd6f217f85f0582a6947dd6fce8036b8ed81b5`；detach Receipt
  `f4ca1d45-b002-47d2-b56a-15f6b57f7b3b` / hash
  `sha256:2a476a8b1e9f22247726c75ef5dae82eb043b339a501e7ea13b776324c6b48bc`。
- 最终 BR binding rev9/epoch5 disabled/fenced/desired disabled，九路 legacy rev179/group206，
  `resendDisable=false`；唯一 failed attempt及零副作用不变。

## 3/6 BS 创建与 lifecycle

- BS installation `c5a95204-c379-4763-b697-b4417349d204`，generation
  `6f8bcb56-5717-4d7a-9a9e-97c1982db053`，lock
  `sha256:0a3e5483351102d624ea389fafc865266c3ad642c70466068146705d4507c6ec`。
- prepare operation `0587d5e6-1f14-4406-a1e4-95e8e556c583` accepted后，首次 verify 在任何写入前因
  尚无 committed binding 被拒绝；启动唯一新 Host消费同一 prepare并读回 succeeded后，才首次提交
  verify。不存在 prepare重发或未知边界。
- verify `48269712-d160-411a-a75d-de6ec18b926e`、configure
  `d326d4c5-bd40-4a49-9568-149675c2520a`、enable
  `77a24b2b-e611-47a6-90a4-e57e4d0a349b`均正式 succeeded。
- configuration `3ce0182e-57b1-4c14-ad48-54cc4de63dfa` / hash
  `sha256:2c10d539e11a332e9ec27ce31c23d3e4b0b7a0b0b182e32c402c8d32e584e722`；切换前 binding
  rev4/epoch3 enabled/ready。

## 4/6 注册与九路 cutover

- registration Receipt `e3a3a095-7c39-4e03-a0cf-8f893cf36d15`，request hash
  `sha256:024ceb89cfddd06f595211994fad690670646ea88c0725de7adf09314cacb62d`，content hash
  `sha256:0d688ed32317078d28f8eda1794f76de6fcb53ada54566c7d45ab1ba5b0543ab`。
- cutover operation `b193f4ac-449b-494b-a401-800d5699ce59`串行完成 approve、prepare、pause、
  commit、validate、resume；prepare/commit/validate/resume Receipt分别为
  `8e8ff255-1ebc-4fff-af84-c7ea0eb488cf`、`a11c2752-4c42-4916-b5cd-a2f8dfd17adc`、
  `a3cc9e89-033d-4c74-87ee-75001ba8df32`、`ac76a58f-52e3-4c89-bcc9-40852aaf34b3`。
- 九路切换明确完成为 BS extension rev180/group207；claimPaused=false，claimed occurrence/attempt、
  unknown attempt及running runtime attempt均为空。

## 5/6 健康观察停止边界

- 唯一新 Host PID 79229；第二Host=0、18181=0。Host在健康观察达标前的恢复扫描中于
  `require_runtime_role`查询收到 `QueryCanceled`，status-file正式写入
  `SAFE_BLOCKED / HOST_RUNTIME_FAILED` 后退出；不存在存活的Runtime Host。
- 失败前 renewal=4、last sequence=17。Host关闭将 binding推进为 rev7/epoch4
  disabled/fenced/desired enabled/observed unknown；prepare operation推进到 rev20、
  `needs_attention / RESOURCE_CLEANUP_UNCERTAIN`。
- 资源 `eb7c19d7-...`、`fd62f8b9-...` 已 released；`accb54dc-...` 为 uncertain且
  `observed_release=false`。该 generation 禁止原地复活，健康观察未达GREEN。

## 6/6 冻结、验证与下一波

- 最终只读边界：九路仍为rev180/group207；BS attempt=0；12 members、12 running Run、12 Dataset
  Receipt；本快照组 Store Receipt=0、`ecom_link=0`、projection pending=0、canary=0；18181=0、Host=0。
- BS观察器的初版二层wrapper在采样前被固定installation门禁拒绝；已最小修复为直接绑定共享观察器，
  并复用BR已验证的单次端点解析、只读repeatable-read连接。该修复未掩盖真实Host失败。
- 本波 verification 落盘后精确提交；不push、不动其他分支，不读取商城源数据，不调用
  `run_definition`，230 L0继续挂起。
- 下一波自动执行 **BS uncertain-resource 正式退休与 BT direct successor**：先以binding rev7/epoch4、
  apply needs_attention rev20、2 released + 1 uncertain、九路rev180/group207、definition rev127、attempt=0
  为 exact authority，走正式 cleanup/disable Owner路径；只有取得三资源 released及detach Receipt后才创建
  BT，否则继续fail closed冻结。
