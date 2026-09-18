# a0v089 部署与运行基线重载证据

## 范围与规则

本波仅在 `m1` 关闭 runtime attempt 终态原因迁移的真实部署与重载门禁；不创建或重发业务 Run，不手工调用 `run_definition`，不启用安装或 Binding，不读取栖月汇源数据，不把入口可达或测试通过写成经营闭环完成。`230 L0` 保持挂起，不 push。

## 第 1/6～2/6：迁移空窗与部署

- 部署前确认 running attempt=0、running operation=0、enabled Binding=0；`dev-org/dev-project` attempt/Binding 均为 0。
- `a0v_088 -> a0v_089` 结果为 `RUNTIME_ATTEMPT_TERMINAL_REASON_089_GREEN`。
- 迁移 hash：`sha256:c0bc19a21db93674baf0779b6c7a63828befb2d4976509c06168e9df6175049b`。
- 迁移前备份：`/Users/ddt/work/projects/ai_agent/.aos-recovery-20260917/state/runtime-attempt-terminal-reason-deploy/aos_meta_head-before-a0v_089.dump`，9781531 bytes，`sha256:ef92917c011523f292416cf505398661a4d1b007215de2de15d498749551f9ce`。
- schema 读回为唯一 `a0v_089`，四个终态原因列与 head/event 保护均存在；部署器记录 `businessWrites=0/sourceReads=0`。

## 第 3/6：受控重载与 8434 恢复

- 旧 API/Worker 与 Host 收到 TERM 后正常停止；既有 LaunchAgent 只拉起一个 API/Worker PID 52614 和一个 Host PID 52625。额外 Host 启动被单实例锁正确拒绝，未形成双 Host。
- API 监听 `127.0.0.1:18181`；`/v1/health` 与 `/v1/ready` 均为 200。一次 5 秒整包读取 `/openapi.json` 超时曾被误判为无响应；随后 socket 首包在 0.14 秒内返回 200，响应声明约 5 MB，健康端点持续正常，因此不把大文档下载耗时当服务故障。
- 重启后 8434 没有监听。既有证据确认它是 `apps/web` 下的第二个 Vite 入口，不持有独立业务状态。普通后台进程会随执行器退出而被回收，真实浏览器得到连接拒绝；该失败保留为恢复方式不合格的证据。
- 最终将 `com.aos.a0v-web-8434` 注册到 `/Users/ddt/Library/LaunchAgents/com.aos.a0v-web-8434.plist`，固定 Vite 5.4.21、工作目录 `apps/web`、监听 `127.0.0.1:8434`、代理目标 `http://127.0.0.1:18181`。当前 PID 53885、LaunchAgent state=running；日志位于受保护恢复目录 `state/a0v089-reload/`。
- Vite 入口脚本 hash：`sha256:096985df17d3ba02c437de4b25f22cde3c99eb0d958172cac1333ed3feb20220`；配置 hash：`sha256:9f430bc4d523ebcd223b8b22d64db1289d0d0f8d7aabb21bb91ea68a8a64d664`。

## 第 4/6：联合运行验证

- HTTP：18181 health/ready、5173 ontology/API proxy、8434 ontology/API proxy 均为 200；复查时三个端口分别由 PID 52614、33540、53885 唯一监听。
- API preflight 为 `CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN`，`sourceCalls=0/runsCreated=0`。
- Snapshot Worker 为 `IDLE`，任务存活且 `hostInThisProcess=false`。
- Runtime Host 为 `RUNTIME_HOST_ACTIVE`，`tenantCount=1/canaryTenantCount=0/liveTargets=[]`，业务 Worker 清单为 product-event、baseline-assessment、analysis-data-requirement。
- `/v1/me` 读回 `orgId=org-org/projectId=dev-project`；`dev-org` 继续仅作零写 canary。
- IAB 真实刷新 `http://127.0.0.1:8434/ontology`，标题为“本体管理（数字孪生） · AOS”，版本 v1.6.5、对象列表与主导航可见。电商工作台目录读回“暂无可见工作台入口”，与 enabled Binding=0 的安全空态一致；本波不把它记录成八工作台验收通过。

## 第 5/6～6/6：一致性、限制与下一波

本波没有修改产品代码、包锁或业务数据；只新增本证据并恢复本机入口。运行态与 a0v089 方案一致：终态原因 schema 已部署，空运行态重载成功，Host/Worker 分离，正租户与 canary 边界未漂移。

限制：这只关闭 a0v089 部署和重载门禁。尚未执行 AN direct successor，也未形成栖月汇自然 ProductEvent→Case/Run→分析建议→exact 评审→内部任务→受控能力→产物→人工评审续跑→复盘/Wiki 的完整首链，更未完成八工作台连续观察和发布决定。

下一波直接进入 AN：先复核现存 saved-input successor admission 改动与上位 recoverable Store 方案，冻结文件级清单；补齐 Red/Green 与真实 PG 组合测试，确认旧 idempotency key 只读回原 Store Receipt 且不重发未知结果；方案代码一致后才允许准备 AN direct successor 的真实受控路径。
