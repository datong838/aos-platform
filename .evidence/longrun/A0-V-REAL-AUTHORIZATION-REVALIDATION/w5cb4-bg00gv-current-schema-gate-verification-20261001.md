# BG00GV 最新代码版本门 verification

基线7ae0b0f7/AOS-001062。仅修改scripts/a0v_current_preview_http.py与其定向测试，未迁移或重启当前实例。

## RED与实现

旧启动器EXPECTED_SCHEMA_HEAD=a0v_118，即使checkout为130仍给118库预检GREEN。删除静态常量，Alembic ScriptDirectory只读代码目录必须恰有一个head；库alembic_version必须恰有一行且等于该head。错误分别PREVIEW_CODE_SCHEMA_UNAVAILABLE/PREVIEW_CODE_SCHEMA_DRIFT，成功回包含实际核对后的version/codeVersion。未调用upgrade/stamp，源连接仍read_only。

源码复审：只更改预检版本来源，保留签名树、安装approved/四published/零binding、有限身份/OIDC及全部worker关闭条件；原首次安装/Registry的a0v107阶段约束未动。移至模块顶部导入Alembic，避免在AOS日志配置后延迟导入污染CLI单JSON合同，不全局关闭日志。

## 命令与实测

API cwd `.venv/bin/python -m pytest tests/extension_runtime/test_a0v_current_preview_http.py -q`：/tmp/aos-gv-red.log，6 failed/7 passed/4.68s/exit1；新增当前head helper不存在。覆盖旧版、空/多行数据库版本、代码无head/多head拒绝。

最终累计命令：

```sh
.venv/bin/python -m pytest tests/extension_runtime/test_a0v_current_preview_http.py tests/extension_runtime/test_a0v_current_preview_registry_publish.py tests/extension_runtime/test_a0v_current_preview_installation.py -q
```

/tmp/aos-gv-regression-final.log，17 passed/exit0（具体时长见日志）。py_compile与git diff --check exit0。测试用替代输入证明版本比较/分支/签名和身份门，不作为真实安装或业务验收。

真实只读预检（代码仓库cwd）：

```sh
services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json
```

exit2，/tmp/aos-gv-current-preflight-final.json可整段json.load，outcome SAFE_BLOCKED/reasonCode PREVIEW_CODE_SCHEMA_DRIFT。原118当前库未变，当前代码130；不是签名错误，不得回退常量118以使其GREEN。第一次复验因延迟导入多行INFO已在源码修复，保留/tmp/aos-gv-current-preflight.json供排障。

通过docker精确连接独立clone aos_bg00gu_current_20261001，BEGIN READ ONLY读取版本130，将真实版本行交同一个_require_current_schema，返回130，_code_schema_head亦130，exit0。这只证明schema匹配；不宣称clone已通过完整安装/身份/业务门。

现有监听仍API PID65249:8080、Web PID59876:8434；18181无。lsof多端口命令因18181无监听整体exit1，不能误称进程停止。未发reload/stop/restart命令。

## 当前身份实测和恢复限制

.env/apps/web/.env、当前shell均无AOS_OIDC_/AOS_AUTH_键；launchctl print gui/<uid>/com.aos.a0v-api-daily0900 exit0，同样无这些键；旧com.aos.a0v-api-8080 label不存在exit113，其166字节plist不能由plistlib解析，未修改。只提取配置键名，不输出任何凭据。当前API命令行是旧--serve，非--serve-limited。不能据此否认外部IdP本身存在，只能判定已知当前启动配置尚无正式接线。

现有服务维持，未来最新代码启动遇旧库会禁入；安全恢复须先满足独立API身份/外部OIDC配置及当前迁移门。BG00GU当日备份+130克隆已通过，但仍缺零执行窗口和第二停机备份，故没有当前迁移/重启，不把此波算每日最新重启验收。

下一波：当前实例身份来源明确后继续安全切换；等待期间从原Review producer的AnalysisReceipt/GrowthPlan/ReviewIssue/EvalReport/artifact来源接线推进，禁止测试替代充自然首链。BG00GT评测权限方案仍待用户裁决，watchdog未部署，首链/八场景/连续观察/发布仍未完成。Goal active，未push，未启Provider/Host/worker，未读商城源/重放旧12Run/手工run_definition/230L0。
