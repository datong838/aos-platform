# 电脑重启后的当前栈恢复方案（2026-10-02）

用户提示刚重启电脑，授权继续最新代码/权威卷的质量预览恢复。前读：`m1@708cc6ca`，代码迁移头 `a0v_135`；`colima list` 三个 profile 均 Stopped，8080 无监听，8434 仍有旧 node；备份 `aos-recovery/.aos-current-backup-20261002-cutover135/current.dump` 的 SHA256 与当日记录 `8862e763...8188` 一致。当前正式 OIDC/身份/八配置/Owner 不足，Host/worker/Provider 保持关闭。

恢复顺序：启动 `aos-extension`，核原命名卷 `aos-a0v-recovery-pg-data` 挂载后启动 `aos-a0v-recovery-pg`，读回 `aos_current_preview_20260927@a0v_135`；运行最新源码的签名 `a0v_current_preview_http.py` 预检。API 旧 `~/Library/LaunchAgents/com.aos.a0v-api-8080.plist` 实际为 JSON 数组、`plutil -lint` 失败，不能直接 bootstrap；在同一 LaunchAgents 目录新建合法 `com.aos.a0v-api-daily0900.plist`，只指向当前仓库 Python 和原签名 Receipt，不内嵌账号/密码。Web 先 bootout 原服务再 bootstrap 原有效 plist，避免旧 Vite 进程冒充最新页面。API/ Web 要回读新 PID、18435/8080/8434、健康/ready/八路由、安装和配置只读状态，浏览器验收禁入并留证据。

不迁移、不删除任何库/卷/备份，不读取商城源，不启动18181，不回放旧12 Run，不手工 Run。若正式预检或版本不一致则停在失败封闭状态，查明后再启动；页面 HTTP200 仅是质量预览，不是自然首链通过。
