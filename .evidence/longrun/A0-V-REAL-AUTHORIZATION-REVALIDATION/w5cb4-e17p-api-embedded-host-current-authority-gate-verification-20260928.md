# W5CB4 E17-p｜API 内嵌 Host 当前签名权威门验证

## 改动

- `control_wiring.build_production_runtime_host_selection` 在 Host enabled 分支、依赖/OCI/worker 构造前要求显式当前签名 Receipt 与受保护三身份文件；调用 E17-l 无 shell、60 秒有界只读子进程，只接收退出 0 和精确 GREEN 结构。进一步把 API 主连接的实际服务端地址/端口/库名与签名目标物理 authority 对齐，并核 API bundle/trust 路径等于签名预检路径。缺值/旧库/异常返回固定 INACTIVE；Host disabled 分支不做新增 IO。
- E17-l 预检 GREEN 报告补无密钥 `databaseAuthority`、`signedRoot`、`trustRoots` 供 API 交叉绑定；不增加任何启动能力或数据库写入。
- 测试中的旧 DSN 对仅作为拒绝用例，原依赖构造测试显式替身通过新门后继续检查原平台/UI 接线。替身 GREEN 不作为真实身份验收。

## 本轮证据

| 检查 | 命令/结果 |
|---|---|
| RED | `services/aos-api/.venv/bin/python -m pytest -q services/aos-api/tests/extension_runtime/test_production_runtime.py -k 'enabled_host_requires_current_signed_receipt or enabled_host_failed_current_preflight' --disable-warnings`：退出 1，2 failed，原 enabled 入口在缺当前 Receipt 时仍到选择器。 |
| 专项和相邻累计 | 七个 test 文件联合：`test_production_runtime.py`、`test_ui_read_production_wiring.py`、`test_a0v_current_runtime_host_preflight.py`、`test_runtime_startup_composition.py`、`test_runtime_installations_api.py`、`test_a0v_ecommerce_runtime_host.py`、`test_a0v_current_preview_http.py`；`services/aos-api/.venv/bin/python -m pytest -q <上述七路径> --disable-warnings` 退出 0，108 passed、7 warnings。覆盖缺 Receipt/凭据、旧 DSN、子进程失败、API 同名异物理库、签名目录漂移和 disabled 无预检。 |
| 语法/差异 | `services/aos-api/.venv/bin/python -m py_compile ...`、`git diff --check` 退出 0。 |
| 当前签名安装 | `services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json` 退出 0：当前 `aos_current_preview_20260927@a0v_109`，安装 approved，4 published，binding 0。 |
| API 重新加载 | 旧 8080 PID 14964 收 SIGTERM 后端口退出；`services/aos-api/.venv/bin/python scripts/a0v_current_preview_http.py --signed-receipt ... --serve` 新 PID 25092，启动输出 `migrationMode=disabled,runtimeHost=0,workersEnabled=0`，日志 `startup_extension_runtime_host_inactive code=DISABLED`。`/v1/health` 与 `/v1/ready` 均 HTTP 200；8434 `/aip/skill-publish` HTTP 200。 |
| 数据卷/Host | `docker --context colima-aos-extension inspect ... aos-a0v-recovery-pg`：running true，命名卷 `aos-a0v-recovery-pg-data:/var/lib/postgresql/data`；`lsof -nP -iTCP:18181 -sTCP:LISTEN` 退出 1，无监听。 |

## 限制和风险

当前正式三身份凭据、Host assignment、八类 active 配置与业务审批仍未齐；未对 enabled Host 作真实正向启动，也没有自然首链。此门只防 API 启动路径的旧目标/旧 bundle 混用，不能代替运行操作、权限、预算及 Receipt。通用 selector 现在对 enabled Host 要求当前 A0-V 签名输入，其他部署模式的独立签名授权合同待分波抽象；当前现场 Host 关闭，不影响已运行的 8080/8434。受保护凭据在预检后由既有连接工厂再次读取，未来正式启用前需评估凭据文件漂移的 TOCTOU 风险。`browser-pilot` 当前不可用，未留新截图。
