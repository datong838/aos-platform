# 首次导入凭据加载护栏验证

基线 13a679dc。env_load 在文件发现与 force 前识别 AOS_DOTENV_DISABLED=1；默认不变。live-eval 执行器及本地诊断启动器在首次 aos_api import 前设置。

测试先红 2 项（disabled/force 仍枚举文件），修复后 3 passed。独立真实 package import 输出 INITIAL_IMPORT_DOTENV_DISABLED，_LOADED=false，日志没有 dotenv_loaded。评测 replay-import-guard.json providerCalls=0，日志没有 dotenv_loaded。未重新调用 Provider。

确认原 18181 监听 PID 5188 命令为本地诊断启动器后，TERM 并重启同一入口，新执行会话 79702。数据库和前端进程未重建。以本轮首次导入证据替代先前“导入后 monkeypatch 足以禁用”的错误推断。

Task/Lease：API/tests 沿用 A0-V 主任务，脚本由 A0V-LIVE-EVAL-IMPORT-GUARD 记录。既有测试警告及 JDBC 退出日志错误未处理。无真实数据 mutation，目标继续为完整业务首链。
