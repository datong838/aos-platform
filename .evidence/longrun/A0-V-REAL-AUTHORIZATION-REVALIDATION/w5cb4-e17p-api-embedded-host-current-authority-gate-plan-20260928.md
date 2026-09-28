# W5CB4 E17-p｜API 内嵌 Host 当前签名权威门文件级方案

## 已复习合同与问题

231-2/231-3 要求 signed bundle、当前安装、三身份和有效配置；E17-o 证明 HTTP runtime-apply 只认 API 进程内 ACTIVE Host，而 API `main.py` 通过 `control_wiring.build_production_runtime_host_selection` 选择 Host，没经过 E17-l。当前 preview launcher flag=0，现场安全；若未来只改 flag/凭据，三身份可同指旧 DB 且 selector 不与 API 当前签名安装目标交叉比较。

## 最小代码方案（施工前再核现有测试）

1. 在 `services/aos-api/aos_api/asset_registry/control_wiring.py` 的**enabled Host 分支、任何 RuntimeWorkerDependencies/OCI/worker 构造之前**，要求显式当前签名 Receipt 与受保护三身份凭据引用。用有界无 shell 子进程运行 E17-l 只读交叉预检，避免直接 import 脚本改写 API 进程环境；只接受退出 0 且最后一条 JSON 为精确 GREEN。缺值、旧库、签名/物理库不符、身份/assignment/config 候选缺失或未知错误返回固定 INACTIVE，不能继续 selector。关闭 Host 分支不做额外 IO，保持当前 8080 行为。当前代码只有 A0-V Host 入口需要启用，现场没有其他 active Host；通用 selector 的其他 enabled 部署模式在取得各自签名授权合同前也将失败封闭，明确列为兼容性风险，不以本地 preview Receipt 暗中泛化。
2. 预检还须把 **API 主连接实际服务端 authority** 与签名安装/三身份 authority 比较，并核 API `AOS_BUNDLE_ROOT`/trust root 与已核签名目录相等，否则 API 控制面仍可能写另一库或加载旧包。为此 `scripts/a0v_current_runtime_host_preflight.py` 的 GREEN 报告增加无密钥 authority 供启动侧比较；测试覆盖同名异库/旧 bundle 路径拒绝。输出不含 DSN/密码。
3. 不把预检 GREEN 当 runtime-apply/enable 权限：现有 `current_preparation_executable`、操作 CAS/权限/批准、配置/预算和资源状态门原样保留。E17-m 独立 Host 硬门仍不解除。若发现全局 selector 改动会影响其他已正常部署，应缩到专用 API 启动组合入口并保证**当前**启 Host 无旁路。
4. 测试先 RED：enabled+无 Receipt/仅旧 DSN 在依赖构造前 INACTIVE、read-only 预检异常固定码；disabled 不访问 Receipt/凭据；正向测试只证明选择器继续原合同，不声称真实 Host 或首链。调整现有 fixture 前先逐个读测试，不大范围改写。文件预期 `services/aos-api/tests/extension_runtime/test_production_runtime.py`、`test_a0v_current_runtime_host_preflight.py`，必要时 `test_ui_read_production_wiring.py`；再专项/累计、diff/风险审查及当前只读负向复验。当前库不写、不启 Host。

## 待证风险

`control_wiring` 是通用 Host selector；如何绑定当前 signed Receipt 而不破坏非当前安装需要逐项核代码和测试后决定。尤其不能让 `.env` 任意路径/旧凭据成为授权来源。方案若需修改当前库或启动自然 worker，停止该做法，先完成无作用代码门。
