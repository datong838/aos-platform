# W5c3i 第三个继任者自然 Prepare 方案（2026-09-24）

## 目标

W5c3h `55a8b4ec` installation `407059df-6f1f-4927-acd7-8e388692838e` approved/etag3、predecessor null、lock `sha256:820eb34977f56544428e3ecde4fbbca637d6a8ad9cdbd66d223cbf35d58f7380`；Host PID17302 唯一空载，安全失败诊断已加载。本波仅原 RuntimeLifecycleService 单次 `runtime-apply`，不发 verify/enable/业务 Run，不切九路/调度，不读商城源。

## 串行步骤

1. 复核两失败安装与 DS 均卸载、唯一 Host ACTIVE/空、精确新安装与 lock/etag、operation/binding/resource0、九路9/9 legacy/fenced、12 schedule off、budget rev13/canary0、新 key Command/runtime operation0。
2. 复用 W5c3e 严格包装，独立 0600 state、新键 `a0v-w5c3i-third-successor-prepare-20260924-v1`，只发一次，记录 Receipt/operation ID；未知提交边界只读对账，不重发。
3. 自然 Host 消费，每 50 秒只读采样直到正式 succeeded/failed/cancelled。成功需 applied/etag4、三 held 资源、同 PID 真实 PreparedJob；失败需 exact operation/事件/资源/Host 与 W5c3g 私有安全异常类型+位置，冻结，不发 verify。
4. verification 与 m1 commit；成功下一波单次 verify，失败下一波针对精确根因最小修复与正式退休。

## 停止条件

任何 Host 退出、资源释放/未知、operation 未终态超时、canary/九路/调度漂移，立即 fail closed；不可手工 consume/claim/finish 或重复请求。
