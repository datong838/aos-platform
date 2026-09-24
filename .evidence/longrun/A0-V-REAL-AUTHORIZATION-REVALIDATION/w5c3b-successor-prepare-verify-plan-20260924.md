# W5c3b 唯一 Host 上的新继任者 Prepare/Verify（2026-09-24）

## 前提与授权边界

W5c3a `2164d0cd`：独立 Host 唯一 PID 14022、ACTIVE/`liveTargets=[]`，新 installation `ae42f0e5-270a-4b7b-8a82-fd3bfbb925dc` approved/etag3，DS uninstalled，九路 legacy/fenced、12 schedules disabled、attempt/canary0；旧 terminal outbox 22。此波只走原 `RuntimeLifecycleService.request_preparation` 的 runtime-apply → 自然 Host 消费 → runtime-verify → 自然 Host 消费，不配置、不 enable、不切九路、不调度、不读取商城源。

## 串行步骤与文件

新增 `scripts/a0v_w5c3b_successor_lifecycle.py` 与测试。每阶段独立全新幂等键、私有 0600 intent/result；精确安装 ID、签名 lock、etag、Host PID/ACTIVE/positive tenant/同一 status、旧 DS uninstalled、九路/调度/attempt/canary门禁。用原 activation identity/roles/markings 与 lifecycle Owner `request_preparation` 一次；不得手动 claim/finish outbox。提交边界未知仅按新 key/operation/Receipt 只读对账，不重发。

1. Prepare 前必须 approved/etag3、binding0/resources0/operation0，Host 唯一且 liveTargets0；提交 `runtime-apply`，每 50 秒只读采样精确 operation/安装/Host，直到正式 succeeded/failed/cancelled。成功需 installation applied/etag4、资源 lease 当前 held、Host 同进程 LivePreparedJob 指向精确安装/新 generation；失败/未知冻结，不发 verify。
2. Verify 前必须同 PID ACTIVE、同一真实 PreparedJob、apply succeeded、installation applied/etag4；提交 `runtime-verify`，同样 50 秒只读直到终态。成功需 active/etag5、唯一 generation binding disabled/fenced/ready、资源仍 held、Host liveTargets 精确同一对象；九路/12 调度/业务 Run 不动。
3. 独立 audit 与测试、verification、m1 commit；后续波才 stage/configure/enable 与九路 route、12 条全新 control/definition。Host 退出、lease released、operation 结果未知或业务副作用，按正式 preparation-reset/direct successor 处理，不复活资源、不重发。
