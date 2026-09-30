# W5CB4 BG00ck｜当前 a0v118 安全迁移与最新代码重启方案

接 AOS-000940、m1 `eceea105`。依据231-4/231-6及BG00ce全库恢复演练。当前代码 head `a0v_118`，当前权威卷 `aos-a0v-recovery-pg-data` 上库 `aos_current_preview_20260927` 为 `a0v_117`；8080/8434在运行、18181/Host/worker/Provider关闭。迁移仅加网络审批专用 DB 门与默认 NOLOGIN 角色，不能宣称已具正式issuer/IdP/checker。

1. **基线与一致备份**：确认m1唯一写者、精确代码HEAD、当前卷/库/迁移、安装签名Receipt、API/Web监听与零业务执行。先停止 API/Web 以建立零执行窗口，PG保持运行。当前库只做一致 `pg_dump -Fc` 与 `pg_dumpall --globals-only`，私有0700目录/0600文件，SHA256/TOC/权限/来源回读；绝不打印globals敏感内容，不删除旧备份。备份期间不读商城源明细、不回放Run。
2. **独立恢复与迁移演练**：在 test-only Colima 的独立PG16容器/卷恢复同一备份与无密码 globals/必要角色 membership；全库 `pg_restore --create --exit-on-error`，当前库和克隆六张控制表行数/全行摘要一致，a0v117。再用最新m1精确 Alembic `upgrade a0v_118`，检查角色 NOLOGIN/NOINHERIT、两个 trigger、普通runtime负例、通用Action不变、schema版本与安装签名预检。BG00cj专项目前只允许旧克隆容器名；精确扩展 `services/aos-api/tests/aip/test_aip_network_policy_approval_issuer_pg.py` 的白名单到本波新隔离容器，禁止任意目标，且运行时仍设 `AOS_TEST_USE_SHARED_DATABASE=1`。不能拿前波旧克隆的手工 SQL 应用代替本次全链演练。
3. **当前迁移门**：仅当新备份可读可恢复、克隆全链GREEN、Host/worker/Provider关闭、审批/网络副作用与worker运行数为0，且当前签名与租户未漂移，才在零执行窗口对当前库执行精确 Alembic `a0v_117→a0v_118`。先测试后操作；失败保留服务关闭并只读对账，不重复未知效果。迁移后回读版本、权限、角色、触发器及控制表行数，不启issuer登录。
4. **最新代码重启与验收**：`scripts/a0v_current_preview_http.py` 当前仍把预期版本固定为 `a0v_117`，其专项测试 `services/aos-api/tests/extension_runtime/test_a0v_current_preview_http.py` 也固定该值；克隆和当前迁移验证后，仅改这两个精确文件为 `a0v_118`，先RED/专项再启服务。使用当前命名卷及最新m1代码重启API、Web；签名预检、`/openapi.json`/八路由与核心只读交互、安装approved/active0/binding0、租户隔离、18181无监听。browser-pilot若不可用只记录HTTP可达，不声称截图/交互GREEN。专项/累计回归与方案/代码复审、verification、D-waves、上下文/Prime、m1精确提交。随后进入BG00cl正式issuer进程/外部OIDC/第二checker，不把DB迁移当自然首链。

受控文件：本方案与verification、上述预览启动器及专项测试、BG00cj专项的隔离容器白名单；必要时只修改恢复脚本的精确缺口。当前真实库迁移属于本独立波，严守一致备份、独立克隆、零执行窗口；不删任何库/卷/备份，不写dev-org，不读商城源，不启自然worker/Provider，不重放旧12 Run，不手工run_definition。
