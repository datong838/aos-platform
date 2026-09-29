# W5CB4 BG00cc｜现有受限 DB 登录隔离验证

基线 AOS-000930、m1 `43149076`、当前真库 `aos_current_preview_20260927@a0v_117` 只读、Host/worker/Provider 关闭。受限凭据来自本机既有 mode600 文件，经项目 `_load_credentials()` 校验；仅在内存中把 DSN 数据库名改为显式 test-only `aos_bg00bx_cutover_testonly_20260930`，未打印/提交 DSN 和密码。所有 SQL 事务 `transaction_read_only=on`，未读商城源。

| 隔离命令/路径 | 输出 | 判断 |
| --- | --- | --- |
| `pg_database` 查 clone | `aos_bg00bx_cutover_testonly_20260930` allowconn=true | 指向测试库，非当前真实库 |
| 现有 NOINHERIT `aos_a0v_runtime_20260912` 直连 clone | `session_user=current_user`，提案/Event/Network head/安装 SELECT 全 SQLSTATE 42501 | 登录自身没有业务表直接权限 |
| 同一登录在只读事务 `SET LOCAL ROLE aos_runtime` + `org-org/dev-project` GUC | 四表 SELECT 全可执行；`session_user` 仍为受限登录，`current_user=aos_runtime` | 当前读取路径具备可验证的受限角色基础 |
| 该登录尝试 `SET LOCAL ROLE aos_app` | SQLSTATE 42501 | 无法冒充 owner；未改变角色配置 |
| 采用 runtime 后 `has_table_privilege` | Event INSERT=true、UPDATE=true | 受限登录仍可用普通运行角色直写 Event；不能证明 OIDC 签发 |

复核源代码：`auth.resolve_principal` 的 JWT 验证、`decide_network_activation` 的 OIDC 门和 Store 的网络 checker 检查只覆盖该 API 路径；`aip3_001` 与当前 ACL 允许运行角色直接写 Event，表无网络专用触发器。现有 DB 仅靠 `SET ROLE` 或自行可设置的 GUC 无法区分经正式 OIDC 签发的批准与普通 SQL。a0v116 active DB trigger 不动。没有应用/迁移代码变更，因此本波只报告隔离探测，不称 RED/GREEN 代码开发或业务通过。

补充安全发现：只读静态扫描 `scripts/a0v_w6_bg03_candidate_scan.py:36` 存在硬编码密码字面量；内存比对显示它与当前 mode600 runtime 凭据相同。扫描 14607 个 Git 跟踪文件，仅此路径含该字面量。没有执行历史脚本，也没有在输出或证据写入秘密值。删除当前文件中的值不消除 Git 历史；须在独立安全波先盘点所有运行消费者、保全与轮换路径，再按当前实例零执行/备份/克隆门轮换并清除字面量，核凭据失效与服务恢复。不能以此历史脚本作为现行正式身份来源。

下一波 BG00cd：先完善文件级方案，划定网络 ActionType 的审批写隔离：普通 runtime 保留通用 Action 兼容，但固定网络 Event 的 INSERT/UPDATE 必须拒绝；专用最小授权发行角色只供经 OIDC 校验的入口使用，且受限 API 登录与发行凭据分离。先 test-only 克隆验证安全结构、通用 Action 正例/网络直写负例及合法 OIDC 正例；若无不可伪造来源，保持网络审批/active 禁入。当前真实卷迁移和 API 登录切换仍须独立备份/双克隆/零执行窗口；第二真实 checker、八配置、自然首链仍缺。
