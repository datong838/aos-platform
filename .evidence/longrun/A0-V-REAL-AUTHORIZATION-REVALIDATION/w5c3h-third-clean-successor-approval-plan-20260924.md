# W5c3h 第三个干净继任者仅批准方案（2026-09-24）

## 前提

W5c3g `346864fa` Host PID17302 唯一空载；W5c3b/W5c3e 两个失败安装均正式 uninstalled，DS 亦 uninstalled。失败资源都 released、无 container claim；九路 legacy/fenced、12 schedule off、budget rev13、canary0、业务计数保持。本波绝不重复任何旧键/旧安装准备请求。

## 串行步骤

1. 只读精确核三旧安装 uninstalled/activeRevision null、两次失败 operation/三资源均正式终态且无 running/unknown attempt；Host 唯一 ACTIVE/空，九路 9/9 legacy/fenced、12 schedule off、budget rev13 有效、canary0、四签名包/信任根不漂移、全新 Command 前缀0。
2. 复用原 installer 与 W5c3d predecessor-free 脚本，新增 W5c3h 精确包装与测试；独立 0600 intent/result、新前缀 `a0v-w5c3h-third-clean-successor-20260924-v1`；只创建/submit/approve 一次，不发任何 runtime operation。未知 Command 边界只读对账，禁止重发。
3. 独立 audit 新 installation approved/etag3、predecessor null、签名 lock/四版本/8 模块/四 Command、无 binding/operation/resource/attempt，旧安装仍卸载、Host 同 PID 空载、九路/调度/canary/业务计数不变；verification 与 m1 commit。
4. 下一波才用新 installation 单次自然 prepare，50 秒只读采样到正式终态。若再次失败，优先读取安全错误分类并正式退休，不在同安装重试。

## 停止条件

旧 installation/资源/Host/预算/路由/调度漂移、前缀占用、原 Owner 拒绝、结果未知或新的 runtime 资源出现，冻结，不做业务写。
