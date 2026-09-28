# W5CB4 E17-r｜当前四包启动时签名复验文件级方案

## 方案与现状

231 长程门、E17 当前签名/正式身份清单及 E17-q 审计均要求当前真实制品与正式授权闭环。现有 `scripts/a0v_current_preview_http.py:preflight` 核 Receipt、树 hash、Registry 摘要和安装，但签名只在生成时由 `sign_ecommerce_current_candidates.py` 逐包 `ManifestLoader` + `ReleasePolicy.evaluate` 验证。树 hash 可随篡改的签名一起重算，因此每次启动须复验密码学签名。E17-l/API Host 启动门已复用此预检，补此处即可覆盖两条启动路径。

## 最小实现和文件

1. `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py`：先 RED，构造有正确 Receipt/重算树 hash、但签名被改的受控树，断言预检在连接数据库前固定 `SIGNED_BUNDLE_CRYPTO_INVALID`；保留 Host/worker 关闭断言。测试不得依赖当前真实签名树或私钥。
2. `scripts/a0v_current_preview_http.py`：仅在树 hash 通过后、数据库连接前，按 `builder.ALL_CASES` 使用现有 `FileTrustRootProvider`、`ManifestLoader`、`ReleasePolicy.evaluate` 逐包复验，并与 Receipt 中四个 content hash 对齐。所有校验异常收敛为固定错误码，不输出包内容、trust 内容或凭据；不放宽已有安装/迁移/租户门。
3. 真实当前签名树和库只读正向预检；用临时副本改签名并重算树 hash 做负向复核。专项及邻接回归、代码/方案一致性与风险审查、当前 API 以最新脚本重新启动并回读 Host 关闭。

## 边界与回滚

不读商城源、不写当前库、不启 Host/worker、不重放旧 Run。失败只阻断当前启动；不触碰其他工作树改动。若导入注册表模块会触发 `.env`，需显式保持预检进程 `AOS_DOTENV_DISABLED=1`；检查代码后采用最小隔离。回滚为本波精确代码提交的 revert，旧启动路径将失去每次签名保证，故回滚时应保持 Host 禁入。

## 下波

E17-s 冻结三身份凭据预检至连接期的代次/内容，确保轮换期间安全停机且不泄露密码或可猜测摘要；正式授权/配置仍独立阻断首链。
