# W5CB4 E17-q｜运行签名复验与三身份文件漂移只读审计方案

## 上位约束

231-2 要求运行时签名、当前授权与隔离身份；E17-p 只在 API Host 选择前调用 E17-l 只读预检。此处审查该检查是否真正覆盖密码学签名，以及受保护凭据在预检与后续使用之间是否可能漂移。不改代码、不启 Host、不写当前库。

## 文件级审计

1. 比对 `sign_ecommerce_current_candidates.py` 生成时的 Ed25519/ReleasePolicy 验证，与 `a0v_current_preview_http.py` / `a0v_current_runtime_host_preflight.py` 每次启动的检查；区分签名生成时证明、当前树 hash、当前 Registry 摘要和真正每次密码学复验。
2. 逐行追 `runtime_connections.py:_runtime_file_dsns`、E17-l 预检、`control_wiring.build_production_runtime_host_selection`、selector/worker 连接创建，判断保护文件是否再次读取、能否在选择后替换成另一同结构身份。只读检查权限和实际当前凭据是否存在，不读取旧密钥或输出密码。
3. 给出下一波最小实现与可失败测试：优先复用现有 `ManifestLoader`/`ReleasePolicy` 做当前签名树的运行时密码学复验；凭据冻结/漂移门须在每次连接前约束或使用经过验证的不可变快照，不能仅靠启动时看一次文件。审计结论不等于正向业务验收。
