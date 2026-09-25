# W5ca1 补证｜launchctl submit 自动重启，原“单次进程”判断失效

W5ca2 新鲜门禁时，原失败 label `com.aos.a0v-http-w5ca1` 又显示 PID35932、命令仍为同一专用 wrapper `serve`；18181 没有监听。精确 `launchctl remove com.aos.a0v-http-w5ca1` 后读回 label 缺席、PID35932/其它 wrapper 进程缺席、18181/8080 无监听、恢复 PG 唯一 Up。停止后统计 stdout 中 `STOPPED_FOR_INSPECTION` 记录 **20 条**；这是 label 自动拉起的多次预检失败，虽然 agent 只调用了一次 `submit`，不能再称进程层面单次尝试。原 W5ca1 verification 的“没有第二次提交”仅限 agent 命令次数，不等于托管器没有重启。

错误仍在预检调用 `docker` 时、API listener 之前；未证实每次内部调用的其它全部副作用为零，不用推断代替 readback。此 label 已移除；不能复用 `launchctl submit` 作为无重试启动器。后续只能设计显式 `KeepAlive=false` 且独立验证无自动重启的托管方式，先 plan/测试/新鲜门禁，严守原 A0-V no-authority。
