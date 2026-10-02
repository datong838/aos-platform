# GW-b-2c2c1b3c2c｜当前正式身份与八配置来源审计方案

基线 `AOS-001120`、`aos-platform/m1 27d47fd5`，当前权威库135和本机禁入预览栈今日已重启。复习231/231-1/231-2/231-4、Growth产品来源清单与 `runtime_configuration_candidates.py`、`a0v_current_runtime_host_preflight.py`、`a0v_current_preview_http.py` 后，先做同一当前库的只读精确审计：八类 active 候选、三平面登录角色/文件来源、当前 Host assignment/identity、正式外部OIDC配置存在性、当前 Growth1.13 正式发布/信任根状态。输出仅计数与安全 reasonCode，不输出 Secret/subject/商城源。

若发现可独立修复的代码缺口，先在本文件列具体目标文件/判据/RED，再编码并跑专项与相邻回归；若缺项是外部 IdP 或正式 Owner 权威，不伪造身份/配置，不改当前库，把该实例禁入后转入已登记的原 BI→Stage→Task/Brief v3 安全代码链。浏览器继续读取当前禁入态，不以页面200做首链通过。

本审计不启 Host/worker/Provider，不写 dev-org，不回放旧12 Run，不手工Run，不提升本地Growth签名，不push。完成须写 verification、D-waves、AOS/Prime 与下一文件级任务。
