# W5CB4 BG00dc｜当前正式 Host 与八候选来源审计验证

## 当前签名与运行现场

- `AOS_DOTENV_DISABLED=1 PYTHONPATH=services/aos-api services/aos-api/.venv/bin/python` 调 `scripts.a0v_current_preview_http.preflight(signed_receipt=/Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json)` → exit 0；数据库 `aos_current_preview_20260927`，迁移 `a0v_118`，安装 `ccdcb0f0-1040-4bc6-aa0c-d045f5689813` 为 approved，binding 0，4 个 published 签名包及 trust root 与 receipt 核验通过。该预检含只读数据库核验，不授权启动。
- `lsof -nP -iTCP:8080 -sTCP:LISTEN` → exit 0，API PID 65249；8434 → exit 0，Web PID 59876；18181 → exit 1，无 LISTEN。端口存活不等于当前代码已重新载入或业务首链。
- `scripts/a0v_current_runtime_host_preflight.py --signed-receipt ... --preparation-only` 不提供正式凭据文件 → exit 2，`SAFE_BLOCKED/CREDENTIAL_FILE_REQUIRED`。仓库 `.env` 未配置 `AOS_EXTENSION_RUNTIME_CREDENTIAL_FILE`、`AOS_CURRENT_SIGNED_RECEIPT`、准备态 Host flag；未读任何旧/test-only 凭据正文。这里只能断言**当前受检入口缺引用**，不能断言磁盘任何位置均无文件。

## 当前库只读精确结果

调用 `scripts.a0v_current_preview_bootstrap._connection_parameters()` 建连接，立即 `conn.read_only=True`；精确 `org-org/dev-project` 查询退出 0：全库 `extension_runtime_host_identity=0`；本租户 Host assignment/operation/binding/configuration/enabled binding 全 0。`read_candidates(conn,TenantScope('org-org','dev-project'))` 八项全 0：responsibility_plans、runtime_policies、data_policies、egress_policies、network_policies、quota_policies、budget_policies、budgets。未读商城源、未写当前库。

## 合法来源与判定

签名制品**存在且通过核验**；运行/目录/Web 三身份受保护文件的当前正式引用**未配置**，其当前库 Host identity/assignment **未投影**。这两层缺口独立，不能从签名包或测试替身推出当前 Host 可运行。生命周期 Owner 在 pending apply 后由 scheduler 构造，不是启动前可手填的授权。八候选的正式产品来源沿 E17-w：职责计划 frozen head、运行策略 active head、数据/出口/网络有效 active policy、配额/预算政策有效 active head、预算 Revision 有效 active head；当前全部 0，且候选计数本身不绑定安装或授权。预算 active 有独立审批/Receipt 门，不能以草案替代。

当前实例不具备 Host 正向启动条件；准备态代码门 BG00da/db 只提供安全路径。下波优先做**独立产品配置入口**的首链必要集审计：从当前安装签名产品定义和现有责任方案入口核对哪些字段可由产品事实给出、哪些必须外部 maker/checker 决策；只对可独立项计划/RED/最小实现。正式凭据、Host identity/assignment 的生产与当前库切换另立恢复/授权波。无浏览器截图；本审计无代码修改，RED/回归不适用。
