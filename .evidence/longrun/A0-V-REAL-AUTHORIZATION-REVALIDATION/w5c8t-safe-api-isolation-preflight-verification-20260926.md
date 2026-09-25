# W5c8t｜只读零执行预检器与真实 STOP

## 九步证据

1. 复习 W5c8s `STOP_PROFILE_START`/AOS-000681、AT 保存快照计划、现有纯 HTTP `API_FLAGS` 与 8080 launchd 风险。
2. 方案先提交 `m1@5d275fb6`；只读检查器不带启停入口。
3. RED：模块缺失，3 个测试报 `FileNotFoundError`；不触碰真实服务。
4. 新增 `scripts/a0v_real_profile_preflight.py`：白名单解析 plist 四项执行旗标、launchd 作业、8080/18181、真实 Colima 停止与容器策略证明；只输出布尔与 STOP/候选，异常输出统一 STOP，不回显配置/路径/DSN。`container_policy_proven` 实际收集固定 false，`authorizes_profile_start` 始终 false；本波没有停用/重启任何服务。
5. 专项/相关累计 `17 passed, 7 warnings in 3.81s`；Python 编译及 `git diff --check` 通过；真实 `aos-extension` 继续 stopped，测试专用 profile 运行。
6. 无新增业务 UI；本波真实页面不验收。
7. 复审：恶意含口令 plist 与命令异常测试均未向结果泄露原文，缺任一旗标 fail-closed。脚本读回存在 TOCTOU，只能作为候选路由，不能授权 profile 启动。VM 内容器 restart policy 仍 unknown。
8. 真实现场运行检查器回读 `STOP`：Cron=false/worker=false/Host=0/migration=disabled 均不成立，launchd 未 quiesce、8080 未释放，18181 空闲，真实 profile stopped，container policy 未证明。证据与代码精确提交后更新 D-waves/AOS CAS/Prime。
9. 下一波 W5c8u：方案化 8080 launchd 受控 quiesce、无服务抢占的纯 HTTP 切换与 VM 内容器策略证明；未证前不启动真实 profile。

本波不读商城源，不迁真实库，不触碰原 12 Run，不回填/ACK；230 L0 挂起、dev-org 零 canary、unknown 不重发、不 push。
