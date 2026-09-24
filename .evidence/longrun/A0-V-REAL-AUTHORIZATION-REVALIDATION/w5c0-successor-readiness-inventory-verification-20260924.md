# W5c0 Direct Successor 前置只读清点验证（2026-09-24）

## 结论

**只读清点 GREEN；业务恢复未开始。** DS `c6812824-a0c3-4adc-9ebc-d56178ae135c` 精确满足原 `replacement_ref()`：active/etag5、overlay `a0v-canonical-ecommerce-v1`、lock `sha256:1b8468b86496b277a0ecd3a802379b3640e5ed1ec76e9ec420b9d15089013938`；generation `b59582cc-2abf-472d-8f59-bfc8be1138c8` 的 binding rev13/epoch7 disabled/fenced/unknown、config rev2。8 个 operation 全终态（旧 enable cancelled，新 disable succeeded），3 lease released，active attempts=0，canary=0。旧 definition rev3 disabled，新 definition 不存在；12 schedule 全 disabled。

## 独立门禁

- 九路当前 dispatch 9/9 `legacy`/fenced/无 installation/generation/epoch，group revision 365；历史 activation `881ef400-d499-4f7b-b08e-6c1891d6122d` 的 lifecycle 1/1 detached，fence/detach Receipt 各 1，claim gate 0。
- DS 的 12 条 selection/control 均只有 rev1，selection `expiresAt` 全为 2026-09-23T11:59:16.071907Z，已经过期；12 schedule 未启用。不能借旧 selection/controls 继续新代际。
- 当前治理：Budget policy head rev13，有效至 2026-09-25T02:52:33.666717Z；RuntimePolicy rev13、Price/Model/Route head 均 rev12。预算此刻有效，但不是永久授权，后继启用前必须再验。
- 签名包目录、信任根和 runtime 身份文件存在，只证明静态材料可定位；进程核验只有 8080 API，18181 与独立 Runtime Host 均未运行，故 **LivePreparedJob=0**，不能直接 enable 原 DS，也不能把磁盘包等同活实例。
- `dev-org/dev-project` installation count=0，未读商城源数据、未新增任何安装/业务 Run/授权效果。

## 下一波精确任务

W5c1 先方案，沿原 InstallationService 用 DS 的不可变 predecessor ref、现行已签名包与全新幂等键创建一个 **approved 但不激活** 的 direct successor；独立回读新 installation、签名/版本/lock/Receipt，期间 DS 仍 active/disabled/fenced，九路和 12 schedules 不动。W5c2 才能在继任者已 approved 且 predecessor detach/资源/attempt 全绿后正式卸载 DS，并启动唯一独立 Host 连续完成 prepare/verify；后续配置/启用、九路切换、12 条新控制链分波执行。若 W5c1 结果未知，先冻结再只读对账，不重发。
