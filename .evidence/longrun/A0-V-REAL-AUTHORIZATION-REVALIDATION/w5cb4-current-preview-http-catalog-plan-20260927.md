# W5CB4 当前新实例安全 HTTP/目录预览计划（2026-09-27）

- 上位依据：231 的 BG-00 产品入口与可禁入要求；当前新实例唯一安装 `approved`、Runtime binding=0、八类配置权威缺失。旧 8080 指保留迁移克隆，前端 8434 可达但目录 `MANIFEST_INVALID`；原因之一是当前 Registry immutable source alias `a0v-current` 未列入 Bundle allowlist，不能改签名/权限门来掩盖。
- 文件级：`services/aos-api/aos_api/asset_registry/control_wiring.py` 只在显式 `AOS_BUNDLE_ROOT` 时增加 `a0v-current` 同根 alias，并补 `services/aos-api/tests/asset_registry/test_control_wiring.py` 正负测试；新增 `scripts/a0v_current_preview_http.py`，仅允许精确新库 a0v_106、四 published、唯一 approved、当前 trust/root/Receipt 匹配、18181 无第二 Host；所有 Cron/worker/Host 显式关闭，迁移 disabled。相关专项与浏览器验收结果落 verification。
- 切端口先读回 PID/命令，TERM 只针对旧 8080 预览进程，不删目录/库/卷；新 8080 必须 health 200、目录真实结果及禁入语义。若前端仍报错，按 HTTP/manifest/权限具体错误修最小改动，绝不声称八页可用或开启 Runtime。8434 不重启，原克隆/日志保留。
- 方案/代码复审、专项与累计回归、浏览器截图/AX 证据、verification、m1 精确提交；结束立刻回 P2g30b 或 Runtime 配置入口下一波。
