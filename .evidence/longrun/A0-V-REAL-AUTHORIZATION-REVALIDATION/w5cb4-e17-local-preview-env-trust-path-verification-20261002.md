# E17 本机预览 .env 信任根路径修正验证

按同名前缀文件级计划，只改被 Git 忽略的 `.env:118`。旧 `AOS_BUNDLE_TRUST_ROOTS_FILE` 指向不存在的 09-10 历史路径（`test -f` exit1）；新路径为当前 pinned preview signing Receipt 已回读的 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-state/trust-roots.json`，文件存在，SHA256 `ed15b78ab7761f85fc9507b9dc5ff0f512bd204010cbd0856787a25962d7abdc`。同文件 `AOS_BUNDLE_ROOT` 仍指向该 Receipt 的 signed tree，存在。未输出或复制 `.env` 其他内容。

- `dotenv_values('.env')`：两路径存在；`rg '^AOS_BUNDLE_(ROOT|TRUST_ROOTS_FILE)=' .env` 仅回读两行，符合计划。
- `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt .../signing-receipt.json`：exit0，`CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、库/代码 `a0v_135`、安装 approved、published4、binding0，签名 trustRoots 与新 `.env` 路径一致。
- API `/v1/health` 与 `/v1/ready` 仍200；内置浏览器 reload 后 37 项仅评测/0发布、三 blocker、按钮 disabled、电商导航无可见入口。
- `git check-ignore -v .env` → `.gitignore:24:**/.env`；此本机配置不随 m1 代码提交，计划/验证证据会提交。若换机器，必须根据**该机当前正式或 pinned Receipt**重新配置，不能沿用本机路径。

这只是本机预览配置自洽，不是 Growth1.13 正式签名来源，也不为受限 API/Host 提供外部 OIDC、独立身份、Owner/八配置或运行授权。真实库只读，Host/worker/Provider 仍关，无商城源读取、旧12 Run重放、手工Run或 push。
