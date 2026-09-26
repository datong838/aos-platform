# W5cah｜原 12 Run 退休方案暂停核验（2026-09-26）

## 结果

**未执行退休，未改业务库。** 本波先行方案为 `17e6b469`。用户随后明确调整优先级：已有可信主要数据足以作为首链候选时，不再死磕失败快照的每行/边缘收尾；先推进更核心的自然业务链。故本波停在方案阶段，原 12 Run 正式退休改列待办，不构成 A0-V/A1 完成证据。

## 新鲜只读检查

- m1 前置 HEAD `74af2bef`、提交方案后 `17e6b469`；原有两个 `w5c8i` 未跟踪文件保留。无 push。
- 本机 `launchctl list` 中只有 A0-V 纯 HTTP 诊断入口 `com.aos.a0v-http-w5ca3` 运行，未看到 Runtime Host job；`ps` 只有该 HTTP 进程和隔离 Colima hostagent/SSH mux；`colima-aos-extension` 仅 recovery PG 容器运行。这些只证明检查时本机观察，不证明持久排他或正式退休资格。
- 用户确认执行部署范围仅当前 Mac/Colima。发现 `/Users/ddt/Library/LaunchAgents/com.aos.a0v-api-8080.plist` 配置 `RunAtLoad=true`、`KeepAlive=true`，尽管当时未加载；本波没有停用或删除它。未做真实 PG closure `prepare/apply/audit`，没有第二次 attempt。

## 后置待办与主线

旧 group `081cd331-cdf8-5bdc-891e-e3b82baa77c7` 仍按上一轮只读证据视为 12 running、原 attempt failed、rev4 disabled；重新行动前必须再读最新 DB，不能拿旧读数授权。待办：枚举并可持续围栏本机全部旧执行入口、fresh Owner 严格门、唯一 key 单次 closure、独立审计、后续 definition 退休；未知结果不重试。不得用这组失败结果作为数据成功或自然链证据。

下一波转向 231 A1/BG-01/02 的最小首链施工：先盘点已有可信商品/店铺 Receipt 与事件→Occurrence→Case/Run 的现有代码、缺口和文件 hash；只编码不依赖当前失败组结果的窄桥接。真实自然执行仍受 A0-V 现行授权门约束，不能靠隔离测试冒充。无关商城全表补齐/原始行证明、八页视觉边角和旧 PG 测试措辞列为待办代查，不占首链阻塞位。
