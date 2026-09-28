# W5CB4 E17-q｜运行签名复验与三身份文件漂移审计

## 签名事实

`sign_ecommerce_current_candidates.py` 在生成时以 Ed25519 签名四包，并用 `ManifestLoader` + `ReleasePolicy.evaluate` 逐包验证当前 trust root。`a0v_current_preview_http.py:preflight` 每次只检查 Receipt 的 `SIGNED_TREE_GREEN`、签名目录树 hash、Registry 四包 contentHash/status、当前安装/迁移；它**没有**在这条启动预检中重新执行 `ReleasePolicy.evaluate`。真实 Host 后续的 release revalidator 仍有签名门，但“启动前四包密码学有效”不能仅由 `SIGNED_TREE_GREEN` 字符串或树 hash 推论。

本轮另以当前 `/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-state` 只读加载 trust roots、四包和现有 `ReleasePolicy`，逐包 `evaluate(...checked_at=datetime.now(UTC))`：退出 0，`{'cryptographicReleaseChecks': 4, 'result': 'GREEN'}`。这是当下独立复核，不等于启动路径已自动做该检查，也不等于 Host/首链授权。没有读取私钥。

## 凭据漂移事实

E17-l 子进程通过 `_runtime_file_dsns` 一次读取 0600、当前用户所有、非 symlink 的三身份文件并用三 DSN 实际连接。E17-p 的 API 父进程收到只读报告后，`select_production_runtime_host` 通过 `runtime_directory_connection`、`runtime_worker_connection`、`runtime_web_identity_connection` 再次读取同一路径；运行期 worker/Host lease 新连接也会重新调用 `_runtime_file_dsns`。文件若在预检后替换为另一份同结构 0600 内容，既有路径没有内容代次/摘要冻结；API 主库和 bundle 的启动时交叉比较也不会自动约束后续文件字节。这是 TOCTOU 缺口，未进行替换实测或真实凭据试验。

## 下一波分解

1. E17-r：在 `a0v_current_preview_http.preflight` 与 API Host 当前门中复用 `ManifestLoader`/`ReleasePolicy` 做每次启动的四包密码学复验；测试篡改 signature 后即使重算树 hash 仍拒绝，当前真实签名树只读正向复验。先方案、RED、最小实现。
2. E17-s：设计并验证受保护凭据预检后冻结/每次连接校验，要求不会把 DSN/密码或其可离线猜测摘要暴露到状态、日志或 API；测试预检后替换/同结构内容变更拒绝，考虑长运行期轮换与安全停机。当前未取得正式凭据，不能用旧文件完成真实正向。

当前库只读；8080 Host 仍 DISABLED、18181 关闭；不碰 dev-org、商城源、旧 12 Run、230 L0。`browser-pilot` 截图待补。
