# W5CB4 BG00ce｜当前 runtime 凭据安全轮换独立波方案

## 权威与理由

按 AGENTS.md、231/231-5 身份/恢复合同及 BG00cd 证据，当前 AOS-000933、代码 m1 `9d27d1b0`、权威卷 `aos-a0v-recovery-pg-data`、真实 DB `aos_current_preview_20260927@a0v_117`。Host/worker/Provider关闭，当前 PG 三 Runtime Host 登录会话0；8080 预览 API 使用 `aos_app`，不使用本次 runtime 登录。历史源码字面量已移除，但该 runtime 密码仍有效，必须轮换。角色密码为 PG cluster 全局，任何在共享 cluster 的 test-only 数据库 `ALTER ROLE` 都会影响真实实例，禁止这样演练。

## 文件与执行顺序

1. 新建仅本波使用的离仓 mode700 状态目录，所有备份/密钥文件 mode600。停执行前只读回读 m1、权威卷挂载、DB版本、签名安装/Receipt、Runtime Host禁入、三身份活跃会话和端口。若漂移即停。
2. 用当前容器 `pg_dump --format=custom` 做**新**当前库一致备份，另用 `pg_dumpall --globals-only` 备份角色/密码哈希及 membership；记录大小、SHA256、`pg_restore --list` TOC、可解析角色清单，不在日志/仓库打印哈希或密码。原角色密码可由既有 mode600 文件回滚；该文件切换前另做 mode600 私有快照。
3. 在 `colima-aos-a0v-test-only` 单独新建 PG16 容器/数据卷，随机管理密码只在私有 mode600 文件，以 `POSTGRES_PASSWORD_FILE` 路径挂载（不入命令参数/环境值/日志）。导入无密码 globals 结构与当前库完整 dump；在独立 cluster 设原 runtime 密码，验证旧登录、角色权限/租户只读路径；轮换为新随机密码，验证旧密码拒绝、新密码连接/角色 membership/权限，回滚旧密码并再验证，新密码失效。演练不得读商城源或业务表内容。
4. 当前切换前复核 API/Web 重启办法、停 8080 API、确认 Host/worker/Provider与18181关闭、三身份会话0和新备份完整。仅对现有 `aos_a0v_runtime_20260912` 执行单条 `ALTER ROLE ... PASSWORD ...`，新随机密码仅存在内存与私有 mode600 临时文件；原子替换既有 mode600 三身份文件的 runtime entry，web/directory保持；严禁展示 DSN/密码。若 ALTER、文件替换或验证失败，按私有快照恢复旧角色密码/文件，重启原服务并报告。
5. 新 runtime 身份连接当前 PG只执行 `SELECT current_database(),session_user,current_user` 及会员/租户只读权限检查；旧密码必须以认证失败明确拒绝。web/directory原身份可连接且角色未变；当前库版本/安装/签名/Receipt/关键表摘要未变，API/Web恢复、18181与Host继续关闭。留记录每步退出码及无密钥哈希。再清点工作树当前密码字面量0；Git历史旧值保留但已无效，单列后续历史访问治理。

## 停线与回滚

独立容器恢复/轮换/回滚任一不通过，不进入当前切换。角色权限/会话/运行开关漂移、备份不可校验或当前实例并发执行时停在只读证据。未知 ALTER 结果只读以新旧密码双向认证探测后决定，不盲重发。不得删除任何现有库/卷/备份，不 push，不改网络批准 Event/active DB 门。API 超级用户登录仍是独立后续风险，不能以本波轮换称其已收紧。
