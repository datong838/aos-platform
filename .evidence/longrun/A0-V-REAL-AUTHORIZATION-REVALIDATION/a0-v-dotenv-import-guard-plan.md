# 首次导入前禁用 dotenv

修改 services/aos-api/aos_api/env_load.py，新增 AOS_DOTENV_DISABLED=1 显式入口，在 _LOADED/force/文件枚举之前返回。默认行为不变，force 不得越过显式禁用。

修改 scripts/a0v_exact_text_live_eval.py，在任何 aos_api import 之前设置该非敏感配置；同步本地恢复目录 start-diagnostic-api.py，在首次包导入前设置。新增 services/aos-api/tests/test_env_load_disabled.py，直接按路径加载模块，避免测试自己触发包副作用；使用禁止文件枚举回调证明 disabled 和 force 均不读文件，并测试默认加载合成配置仍正常。

再启动独立进程实际 import aos_api，以缺失 dotenv_loaded 日志和 _LOADED=false 证明入口生效。已有服务只在确认原会话后重启同一诊断进程，不重建数据库，不调用 Provider。旧证据中的禁用结论以本次验证为准。
