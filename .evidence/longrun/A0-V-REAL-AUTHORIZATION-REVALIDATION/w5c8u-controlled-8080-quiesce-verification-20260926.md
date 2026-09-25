# W5c8u｜8080 launchd 精确停用与真库继续 STOP

## 九步证据

1. 复习 W5c8s/t、AOS-000682、AT/AS 事故、当前 m1；真实 `aos-extension` 停止。
2. 方案先提交 `m1@9f3499d3`，仅授权精确 `com.aos.a0v-api-8080` 作业 bootout；本机 API 暂不可用是预期影响。
3. 只读前检：launchd `PID 1265`/exit 0 与 8080 监听 `PID 1265` 一致；命令是仓库 API venv 的 uvicorn、CWD 为本仓库 `services/aos-api`；18181 空闲，真实 profile stopped。
4. 单次 `launchctl bootout gui/501/com.aos.a0v-api-8080` 返回 0；没有 `pkill`、广泛进程匹配、修改 plist/凭据、启动 VM/DB。
5. 回读：launchd 精确作业不存在，8080/18181 无监听，真实 `aos-extension` 仍 stopped；`aos-a0v-test-only` 保持运行。W5c8t 预检器给 `launchd_quiesced=true`、两个端口 free，但四项旧 plist 零执行旗标仍 false、container policy unknown，整体 `STOP`/`authorizes_profile_start=false`。
6. 8080 API 因受控停用暂不可用，不填浏览器/真实业务验收 GREEN。
7. 离线 VM 目录只见 raw GPT disk，`guestfish`/`qemu-img` 不可用；从 Colima YAML 无法证明 Docker 容器 restart policy。不能以 API 停用替代容器策略证据，也不能靠启动真库后再观察是否自启。旧 plist 的 Host/worker/Cron/迁移风险依然存在，禁止在真库启动后直接 bootstrap 旧作业。
8. verification/m1 提交，D-waves/AOS CAS/Prime 更新；未新增代码，本波测试 N/A。凭据明文/先前终端误输出风险仍待受控轮换，证据不含口令。
9. 下一波 W5c8v：先设计 VM 容器 restart policy 的**无执行副作用**取证和 8080 纯 HTTP 配置改造/恢复；策略未知则保持 `STOP_PROFILE_START`，不迁真库、不扫描/回填/ACK。

恢复 8080 仅在真实 profile 仍 stopped 且确有需要时，可用原 plist 精确 `launchctl bootstrap gui/501 /Users/ddt/Library/LaunchAgents/com.aos.a0v-api-8080.plist` 并读回；本波未执行恢复。230 L0 挂起、商城源不读、dev-org 零 canary、unknown 不重发、不 push。
