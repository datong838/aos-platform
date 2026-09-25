# W5c8u｜真实 8080 launchd 受控停用与容器策略停线

## 基线与授权边界

承接 W5c8t `m1@f9dd90e7`/AOS-000682。真实 `aos-extension` 停止；8080 `com.aos.a0v-api-8080` 被 launchd `KeepAlive` 保活且 Host/worker 开启。用户曾明确允许关闭/重启 8080，并授予 AOS 开发操作；本波只停用**该精确 launchd 作业**，不杀广泛进程、不修改 plist/凭据、不启动真库。此动作会使本机 AOS API/前端依赖暂时不可用，须在证据中明确；若检测到 PID/作业不一致或他人改动，STOP 不操作。

## 文件级与运行步骤

- 先读回 `launchctl print gui/501/com.aos.a0v-api-8080`、8080/18181 PID、命令/CWD、`colima list` 与 W5c8t 检查器；仅输出允许名单字段，绝不打印内嵌 DSN 或 plist 全文。
- 仅当 job/PID/端口一一对应时执行精确 `launchctl bootout gui/501/com.aos.a0v-api-8080`；读回作业消失、8080 端口释放、18181 空闲、真实 profile 仍停止。若端口被其它进程接管或 bootout 结果未知，冻结并停止，不重试杀进程。
- 回滚预案：只有真实 profile 仍 stopped 且确需恢复 API 时，才能以原 plist 精确 `launchctl bootstrap gui/501 /Users/ddt/Library/LaunchAgents/com.aos.a0v-api-8080.plist`，并读回唯一 PID/8080；由于原配置仍含 Host/worker 开关，**不得在真库 profile 启动后回滚旧 job**。
- 容器 restart policy 仍未知：查离线 Colima 元数据/历史证据，若无权威证明则保持 `STOP_PROFILE_START`。本波绝不以“8080 已停”当启动授权；不迁 096/097/098、不读原 12 Run/商城源、不回填/ACK。

## 九步

1. 复习上位/产品、当前 HEAD/launchd/profile/PID。
2. 本方案先提交。
3. 精确只读前检，PID/作业/端口不一致即 STOP。
4. 单次 bootout，未知结果不重复；无代码改动。
5. 作业/端口/profile 回读与静态证据对账。
6. 浏览器 8080 暂不可用如实记录，不伪造验收。
7. 复审是否仍有自动启动路径/容器策略未知。
8. verification、m1/D-waves/AOS CAS/Prime。
9. 自动 W5c8v：针对容器 restart policy 制定不执行 worker 的取证办法；未证前不启动真库。另立凭据轮换门。

230 L0 挂起、dev-org 零 canary、unknown 不重发/不手工 `run_definition`、m1 单写不 push。
