# E17 当前正式启动边界审计与文件级方案（2026-10-02）

## 上位合同与范围

复习 231 主计划、231-2 签名/OCI 准入、231-3 安装状态机、231-5 原来源与首链、E17 当前签名根和三身份清单，以及 BG00gw 当前清单。目标是判明当前预览栈能否承接 Growth 1.13 正式发布、binding 和 Host；只读审计，不改真实库、身份、签名或运行开关。

## 当前事实和可复核命令

1. `git status --short --branch`：`m1` ahead 2744，HEAD `ef2e7797`；浏览器插件与 `pnpm-lock.yaml` 既有改动、历史未跟踪文件保留。`memoryctl.py status --json`：Authority `AOS-001138`，强一致投影 CURRENT；`leases.json` 初始为空。
2. `ps -p 53331 -o command=`：当前 8080 API 是 `scripts/a0v_current_preview_http.py --signed-receipt ... --serve`，不是 `--serve-limited`。`lsof -nP -iTCP:8080 -iTCP:8434 -iTCP:18181 -sTCP:LISTEN`：8080/8434 有监听，18181 无监听；`curl` health、技能发布页均 200。页面/200 不证明正式身份或首链。
3. `rg -n 'a0v_current_preview_http|serve-limited|CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN|PREVIEW_DATABASE_DRIFT' scripts services/aos-api -g '*.py'`：本仓库当前实例的受限 API 和 Host 预检都依赖同一预览签名预检。`scripts/a0v_current_preview_http.py:141-148` 固定 **binding=0、四个发布版本、精确旧版本/hash**；Growth 1.13 正式增加版本或形成 binding 后，若仍用此预检，将失败关闭为 `PREVIEW_DATABASE_DRIFT`。这是由代码谓词推出的未来兼容问题，尚未在当前真实库做发布/绑定实验。
4. `scripts/a0v_current_preview_http.py:212-247` 的 `--serve-limited` 先要求外部 HTTPS OIDC，再调用同一子进程预检和独立 API 数据库登录。当前 `--serve` 不能替代正式受限 API。`scripts/a0v_current_runtime_host_preflight.py:107-156` 要求凭据文件、三独立身份、精确 assignment/identity 和八配置；准备模式也不豁免身份/assignment。
5. `scripts/a0v_ecommerce_runtime_host.py:386-393`：即使上述预检通过，独立 Host 启动器仍无条件 `FORMAL_OWNER_AUTHORITY_UNPROVEN`。这是明确保留的正式 Owner 门，不能删除常量当作准入。现有测试 `test_current_preflight_green_is_not_formal_owner_authority` 固定了这一边界。
6. 现有 `sign_ecommerce_growth_1_13_candidates.py` 自称 **Local isolated signer**，设置本地 key ID；旧 `sign_ecommerce_current_candidates.py` 会在仓外新建本地 key/trust root。两者的测试/本地签名都不能自动成为当前正式信任根。D-wave 当前真实库只读对账：Growth 1.13 当前发布、binding、Host assignment/identity、八类配置全为 0，受限 API/Host 预检分别 exit 2 `EXTERNAL_OIDC_CONFIG_REQUIRED` / `CREDENTIAL_FILE_REQUIRED`。
7. `AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python -m pytest -q` 加三文件 `test_a0v_current_preview_http.py test_a0v_current_runtime_host_preflight.py test_a0v_ecommerce_runtime_host.py`：55 passed、7 warnings、exit 0。此验证只覆盖现有禁入合同，不证明正式启动路径已实现。

## 下一最小施工卡

1. **正式制品与信任源**：先取得当前实例的外部正式 signer/checker、批准 release/签名/OCI/Registry lock 及其代次；读回 Growth 1.13 对应精确 hash。不得把仓外本地签名树直接提升到正式当前信任根。
2. **正式 API/Host 启动兼容**：在 `scripts/a0v_current_preview_http.py`、`scripts/a0v_current_runtime_host_preflight.py`、`scripts/a0v_ecommerce_runtime_host.py` 及三份对应测试前，先写文件级设计：保留现有 pinned 预览谓词；为正式模式提供由当前 Registry/安装/lock/信任根证明的版本集合与绑定核验；受限 API 保持外部 OIDC/非特权独立身份。RED 覆盖 Growth 1.13 当前发布和 binding 的合法准入、缺签名/错代次/跨租户/旧预览身份拒绝。不得仅将 `len(versions)==4` 或 `bindings==0` 改宽。
3. **Owner 准入**：复用 231-3 原安装 lifecycle、强 ETag、批准/verify/enable Receipt、同代 binding 和 `org-org/dev-project` assignment；在同事务读回当前 Owner 后才替换独立 Host 启动器的无条件禁入。RED 覆盖无 Owner、撤销、错安装/代次、跨租户及未知提交。无正式身份时仅在可销毁 PG 完成代码验证，当前 Host 保持关闭。
4. **八配置合法来源**：按 `runtime_configuration_candidates.py` 八个原表的生命周期/生效期做真实产品入口与双签/预算证明；候选数不是配置绑定许可。随后独立零执行窗口完成当前库版本/备份/克隆/切换门，再有界启 Host、自然首链。

本审计为方案/风险识别，不是代码修复或当前实例准入；Goal 继续 active，E17 当前实例仍失败关闭。
