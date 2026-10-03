# s3o-w-y 第一切片 verification｜BI 私有进程启动门

- 基线 `m1@9d9b0d92`、Authority `AOS-001239`；方案 `w5cb4-e17-s3owy-bi-process-admission-plan-20261003.md` 先于代码。RED：`test_aip_bi_plan_issuer_process.py` 缺模块，exit1。
- 新配置强制不同 API/issuer UID、当前 issuer UID/GID、精确 BI 专用 DB 配置及 TenantScope、绝对私有路径、最多64连接/30秒等待。启动先核外部 OIDC、0700 attempt 目录、BI 只读 DB 连接实际身份；所有前门通过后才复用既有私有 listener 的 0750 socket 目录与0600凭据保护。没有 accept/dispatch、没有默认 owner DB、没有 HTTP/Host 启动。
- 专项/相邻：`tests/aip/test_aip_bi_plan_issuer_process.py tests/aip/test_aip_bi_plan_issuer_ipc.py tests/aip/test_aip_bi_plan_issuer_connection.py tests/aip/test_network_issuer_process.py` 46 passed，exit0。socket 目录负例的读连接替身只到路径权限门，不是正式数据库或跨 UID 验收。
- 当前实例只读 `scripts/a0v_current_preview_http.py preflight` + SELECT：库 `aos_current_preview_20260927`、代码/库 `a0v_135`、安装 approved、runtime binding0；`aos_bi_plan_issuer` 角色0、active AgentInstance0、四个 BI 受控函数0，外部 OIDC 配置布尔为 false。当前正式启动必须禁入；没有尝试写库、连接商城源或开启 Host。
- 本机 `sudo -n -l` 输出 `a password is required`，目前不能形成真实不同 OS UID 的正向证据。方案/代码复审：此切片只有受检 listener，无任意 handler 可绕开每请求重验；后续必须显式构造原 Plan 服务/Reader 的 BI DB 工厂、有限 accept 和真实 peer，并在签名隔离库验证未知提交的只读对账。无当前 UI/服务改动，浏览器验收不适用；首链 pending。
