# AZ 保存快照恢复、终态与第二 attempt 冻结验证

## 配置与 authority 转移

- definition rev79 disabled、AZ attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev79 disabled 生成 AZ rev80 disabled，hash
  `sha256:8e26702dc30ee8233393ece3717d4505577ae4d287a0d2c90a8f0231bf67e02b`。
- renew 从 recovery rev25 生成 rev26，hash
  `sha256:30f6fb1491ad4fab6d560a59d642f7d6b3da1e15af05eacee2cd58047178a502`；同一事务生成
  definition rev81 enabled，hash
  `sha256:1e05d2a8ee9f52e64bb5e39ce3782df5c71d9c6cc46323f16e551c1c3b2f499b`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与终态

- 创建 exact `A0V-AZ-SNAPSHOT-WORKER-20260919` deployment lease 后启动唯一自然 snapshot worker；读回
  worker=true/topology=independent、Runtime Host=false、Cron=false，未调用 `run_definition`。
- 自然 attempt `5505b051-79f8-47a7-b2e2-4ddfc0893eb1` 使用幂等键尾号 `:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租并越过
  1800 秒，于 `2026-09-19T14:30:49.838235+00:00` 正式终结为 revision 61
  `failed / RECOVERABLE_INGRESS_DEADLINE_EXCEEDED / IngressJournalConflict`。
- worker 在终态后、停止命令完成前自然领取第二 attempt
  `af15b2e5-7c72-47f0-9e1d-79855a970fd6`，幂等键尾号 `:2`。这触发本波“第二 attempt”停止条件；
  立即停止 worker，18181 释放。进程在端口释放后未完成退出，向已核准的 exact PID 32030 发送 TERM 后仍存活，
  最终 KILL；未生成第三 attempt。
- 第二 attempt 不做业务重放；Runtime Host 的正式过期恢复器在 Lease 到期后于
  `2026-09-19T14:34:11.747510+00:00` 将其收敛为 revision 4
  `abandoned / ATTEMPT_LEASE_EXPIRED`。exact guard 固定验证历史为 1 failed + 1 abandoned。

## 冻结边界

- 最终十二 Run 仍 running、十二 Dataset Receipt 保留；relationship=1、link command=1、linkCount=1168；
  retirement=0、Store Receipt=0、`ecom_link`=0、outbox=0、projection pending=0；AZ 九路与三资源保持，
  `dev-org/dev-project` canary=0。
- snapshot worker 已停止，18181 无监听；唯一外部 Runtime Host 继续运行。definition 暂保持 rev81 enabled，
  但无 snapshot worker。本波不执行 `pause-terminal`，因为第二 attempt 已触发计划的停止条件。
- 当前事实是已知、无业务副作用的冻结边界，但不是成功闭环；下一波必须方案先行，以 exact 两次 terminal history
  为 authority 将 definition 推进到 rev82 disabled，再走正式 retirement + direct successor。禁止重启 worker、
  禁止第三 attempt、禁止手工 `run_definition`。

## 证据与验证

- prepare/schedule/controls/transfer/renew/enable 私有结果 SHA-256 依次为
  `1af33b95e9fbf608e03814b4a1b178aeb2b390c4b9dab36c0282cd2372d99add`、
  `169f2b461cff9392cfdcfcbf348d146aee0139aba92acdc7b1a9ee1ade67e719`、
  `8d17659ac030bb56f9523a143f6ee73643dab2f5e372aec4b94087751ac7904e`、
  `890a23e08b4039609e7e4bc334766f9869117bc580516bf3adfb8acf505739eb`、
  `1ee881949f170fa76472aa024d61baaaef87a266707d7b735915a20498f9ebf2`、
  `1f5a8bd772c91c03824773bd1bcb30fabc26c135a9a30cd41b32fcf2df042881`。
- AZ saved recovery、AZ exact guard 与 snapshot launcher 组合回归 `14 passed`；Python 编译和
  `git diff --check` 通过。

## 下一波

新增 AZ two-terminal settlement 方案；只允许在 exact 1 failed + 1 abandoned、十二 Run running、Store/link/
projection 全零且 worker/18181 均停止时执行 rev82 disable。verification 与提交完成后，才可进入 AZ 正式退休。
