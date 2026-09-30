# W5CB4 BG00ck｜当前 a0v118 安全迁移与重启验证

## 基线与零执行窗口

接 AOS-000940，m1 初始 `eceea105`，代码 Alembic head `a0v_118`，当前权威卷 `aos-a0v-recovery-pg-data` 的 `aos_current_preview_20260927` 起始 `a0v_117`。签名 Receipt 预检起始 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`，安装approved1、published4、binding0。当前 Proposal/ApprovalEvent/active NetworkPolicy均0，其他目标库会话0。`launchctl bootout` 停 API/Web 后 8080/8434/18181 无监听；Host/worker/Provider未开启，没有运行/回放旧Run。

## 新备份与完整独立恢复

私有目录 `/Users/ddt/work/projects/ai_agent/.aos-current-backup-20260930-bg00ck-9us25js3` 为0700。零执行窗口用当前PG容器 `pg_dump -Fc --serializable-deferrable`、`pg_dumpall --globals-only` 生成0600文件；未输出globals的密码哈希。`current.dump` 3,955,407字节，SHA256 `8c609f6fd9a2ab8877b5a6b9665f63b80dc79e8f78c049428e3c34a4197cdce0`；`globals.sql` 4,674字节，SHA256 `0a8c4dc535260acde8285e837305493033042735f875516fb5ce01b0e023ecfa`；`pg_restore --list` 退出0，TOC 5615行。迁移前再次核两文件哈希/0600均一致。没有删除任何旧备份、库、卷。

新建 `colima-aos-a0v-test-only` 的 PG16 容器 `aos-bg00ck-isolated-pg`，独立卷 `aos-bg00ck-isolated-pg-data`、127.0.0.1:18437，管理员密码仅私有0600文件。只在隔离环境把globals中的8处密码替换为NULL、去掉7处原grantor后恢复角色/成员关系，`psql`退出0；原globals原样保留。完整dump执行 `pg_restore --create --exit-on-error` 退出0。源库与新克隆 `a0v_117` 的六张控制表行数及全行摘要6/6相同，私有 `control-digest-comparison.json` 留精确值。

使用最新m1正式 Alembic CLI 对新克隆执行 `upgrade a0v_118` 退出0；克隆升级后六表摘要仍6/6一致，issuer `NOLOGIN`、两触发器存在，Proposal/Event仍0。显式 `AOS_TEST_USE_SHARED_DATABASE=1` 和新隔离容器白名单跑BG00cj专项+网络契约17 passed。这里是新备份全库恢复后的正式Alembic链，不采用旧克隆手工SQL作为本波迁移依据。

## 当前精确迁移与最新服务回读

先把预览启动器的固定版本断言测试改为 `a0v_118`，初次RED为1 failed/6 deselected；最小改 `scripts/a0v_current_preview_http.py` 的 `EXPECTED_SCHEMA_HEAD` 后专项7 passed。联合隔离/启动器专项24 passed，7 warnings，退出0。`python -m py_compile`、`alembic heads=a0v_118`、精确diff check退出0。最小代码与方案复审后m1提交 `0561b921`。

再次验证备份SHA、8080/8434/18181无监听、当前库其他会话0及Proposal/ApprovalEvent/binding/active NetworkPolicy均0；只对 `aos_current_preview_20260927` 运行 Alembic `a0v_117→a0v_118`，退出0。事务内回读 issuer `rolcanlogin=false/rolinherit=false/rolsuper=false`、触发器2；重启后库版本仍 `a0v_118`、卷仍 `aos-a0v-recovery-pg-data`。当前六控制表全行摘要与备份前仍6/6相同，私有 `current-post-migration-control-digest.json` 留精确值。

PG→API→Web 顺序重启。API新PID59645/8080 `/openapi.json`=200；Web新PID59876/8434 `/aip/skill-publish`=200；八工作台HTTP路由各200。签名预检再得 `CURRENT_PREVIEW_HTTP_PREFLIGHT_GREEN`、版本118、approved安装1、published4、binding0。当前库只读tenant聚合仅 `org-org/dev-project` 安装1、active revision0、`meta_membership` owner1；`dev-org`无匹配安装/成员，Proposal/ApprovalEvent/binding均0。18181无监听，最新启动日志 `startup_extension_runtime_host_inactive code=DISABLED` 和worker disabled。

## 判定与剩余风险

本波 GREEN 范围是当前库安全迁移、备份可恢复、精确代码重启和失败封闭。当前API仍用 `aos_app` 超管；issuer仍NOLOGIN，正式外部OIDC与第二真实checker缺失，网络审批正向业务链、八配置、自然首链及八工作台真实交互未证明。browser-pilot未提供，本波只有HTTP路由可达，未做截图/浏览器交互，不称页面验收GREEN。下一波BG00cl接独立issuer进程、SCRAM/HBA与正式人类身份；Host/worker/Provider保持关闭，不读商城源、不写dev-org、不重放旧12 Run、不手工run_definition、不push。
