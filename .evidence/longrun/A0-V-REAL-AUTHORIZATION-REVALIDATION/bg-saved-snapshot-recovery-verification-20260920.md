# BG 保存快照恢复、1800 秒预算与单 attempt 冻结验证

## 配置与 authority 转移

- definition rev100 disabled、BG attempt=0 时启动纯 HTTP 18181；读回 DB migration disabled、QYH Cron=false、
  snapshot worker=false、进程内 Runtime Host=false。系统只有外部 Runtime Host PID 29815，第二 Host=0。
- prepare、schedule-ingest、controls 全部成功，十二 schedule 保持 disabled，全部 `sourceReads=0`；纯 HTTP 端口在
  transfer 前已释放。
- transfer 从 definition rev100 disabled 生成 BG rev101 disabled，hash
  `sha256:bbd263b4e312074b3e7a365cecb7414c55d35340b9fa567a0c224ffe4fceefe6`。
- renew 从 recovery rev32 生成 rev33，hash
  `sha256:c0ac7cfc9e1fa2e573a0c3c61f573511f5e67ef0b15ce7f15927ba08c048ad16`；同一事务生成
  definition rev102 enabled，hash
  `sha256:2e82fa9ac7020581ecef47b4ad2f45fbb3d2d8bf4124da76fad81ac520cd0fff`。enable 读回
  `executionAuthorized=false / original_group_pending`，未提前开始执行。

## 自然 worker 与单次终态

- 创建 exact `A0V-BG-SNAPSHOT-WORKER-20260920` deployment lease 后，由同一 supervisor 启动唯一自然
  snapshot worker PID 87037；读回 worker=true/topology=independent、Runtime Host=false、Cron=false，未调用
  `run_definition`。
- 唯一自然 attempt `a42bc506-7e3c-48cd-bde7-1eb0b1adc93f` 使用幂等键尾号 `:1` 与 request hash
  `sha256:6674e5010b0de24c6740dc383b2f272a8e10fd84b9071cc681e3ad42780c27f7`。它持续健康续租至 revision60；
  supervisor 以数据库 `accepted_at` 为起点，在 elapsed=1800 秒命中预算并在同一进程向 exact worker 进程组
  发送 SIGTERM。
- worker 的受控排空超过原 60 秒等待，supervisor 因等待超时返回失败，并在 finally 再次进入等待；worker 最终
  于 `2026-09-20T01:23:18Z` 完整停止，状态 `STOPPED/taskAlive=false`，18181 无监听。外部 Runtime Host 随后将
  同一 attempt 于 revision61 正式收敛为 `abandoned / ATTEMPT_LEASE_EXPIRED`。
- 全程 attemptCount=1，没有第二 attempt。停止路径已修为单次 SIGTERM、180 秒有界排空，且失败 finally 不再
  重复发送停止信号；该修复只服务后续波，不构成 BG 重试授权。

## 冻结与禁用边界

- exact guard 读回十二 Run running、Dataset Receipt=12、Store Receipt=0、`ecom_link`=0、link outbox=0、
  projection pending=0、dev-org canary=0、九路 BG route current。
- `pause-terminal` 仅在 `ABANDONED_FREEZE_BOUNDARY` 与 attemptCount=1 下执行，生成 definition rev103 disabled，
  hash `sha256:9e74f3052c0a49f66891127f1d1600bd12a066b7f698626d587a248598d49395`；十二 schedule 同步保持 disabled。
- snapshot worker 已停止，临时端口已释放，唯一外部 Runtime Host PID 29815 保持运行。本波没有商城源读取、
  没有手工重发、没有第二 attempt、没有 push，230 L0 继续挂起。

## 私有证据与回归

- 纯 HTTP preflight `b0514c87a524d534a9297258b2667237ed64d1873d3deb4326855773fc624c8b`；worker preflight/status
  `2276b9fe1b051a054ad99d7f0674a0ebbb92973e2d7e6e09c9effe09157b7dea` /
  `e4a6c26042c124fbf6c0592cbd78f86b0a7e5bc31c2b5bb02d269bad78a181f9`。
- prepare/schedule/controls `6f2a5d85e8bd7b2734ed92c9e624eabde4a7f9cac26eae16a317ed860e6219a6` /
  `d7f50c3839b4f3004554c18b933aef03b6390f632bac85f70052bfd022dea622` /
  `e3893545715b059d47ccd2073a994fdf2047ee304f9639cf28dce3fc3bdbc7ab`。
- transfer/renew/enable `adc022f54c28e64f1ea0fd3ee1bfa654011fea68c2a8a869a328c95edd256313` /
  `93e5bd485f9625483ed23a611c9362bbd856dcecc7ca6b67f09d1615f0af4510` /
  `a09e1f897786d44eec7505dbd3467d06a40beda240482292fd912fe40157434e`；pause-terminal
  `fb9b8e266cb78849253323d970846246a7279decedcdf74d985e9d427b449971`。
- BG saved recovery、exact guard、inline supervisor 与 snapshot launcher 专项回归通过；Python 编译与
  `git diff --check` 通过。

## 下一波

新增 BG terminal retirement 方案；只允许在 exact 单次 abandoned terminal、definition rev103 disabled、十二 Run
running、Store/link/projection 全零且 worker/18181 停止时执行正式 disable/fence/detach。verification 与提交完成后，
才可进入 BH direct successor。
