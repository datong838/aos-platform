# 当前135→142正式迁移门实施方案（施工前）

依据231-4共享schema维护门、当前1329及唯一thread/m1；前门5183ed2d/r4完整恢复与fce8c88e独立维护通道全备恢复/配置往返。此plan Task不授权源DDL或停止服务；实现前另登记精确runner/tests/source维护资源Task。保护九M/所有旧卷数据，不push。

顺序：1复核HEAD唯一142、当前135/source容器卷18435、Authority和单写Lease、实际两个叶进程命令归属与所有恢复器。2持久私有intent/恢复配置、拒绝已有attempted/unknown，只有精确原PID/启动时间一致方可停止；不杀WorkBuddy父进程。3当前Postgres容器通过原本地管理员socket设置监听空并实际受控重启（原配置回滚先保存），随后host18435连接实际拒绝/本地维护socket成功，无其他client/prepared、恢复器不能重拉、Host/worker/Provider原关闭证据成立。此实际窗口建立前不执行迁移。4源停止外部写入后全备+globals/ACL/config/序列完整摘要，另一全新无网络/端口目标完整恢复逐项一致；源仅维护连接、禁止其他本地管理写者。5七步原AlembicSQL事务迁移，每步intent/version/done，旧行不变，仅精确2metadata新增/5空表/3NOLOGIN角色，权限保留。6源142全证据成立后恢复原监听配置/受控重启，当前签名/安装状态预检最新HEAD/schema一致，原API/Web单实例原启动路径恢复，PG→API→Web/页面核心功能验收。

失败：维护门不满足不进入DDL；未知结果先socket只读查版本/intent，不重复。已部分迁移不自动downgrade/全库覆盖；保留停机及备份，按原失败版本可恢复SQL门逐步前进，不回放业务。当前原容器的Docker重启策略/保存监听恢复通道、所有有效恢复器、准确API启动参数与签名路径仍需现场只读闭合；未闭合前plan不能声明实施授权或窗口GREEN。严禁把127本地、空连接或default read-only当隔离保证。副作用授权仅维护基础设施，不含Host/Provider/商城源/经营链/外部消息。正式接口/八配置/自然首链仍独立后续门。

未来文件候选：scripts/a0v_current_142_maintenance.py、scripts/tests/test_a0v_current_142_maintenance.py、本目录证据。先真实隔离RED覆盖PID/来源漂移、未知不重跑、TCP未拒绝、其他client/预备事务、备份不完整、原行ACL漂移、schema不一致恢复拒绝；再最小确定性执行器，不能以inline试验直接对当前执行。

## 09:48实地控制路径复核

源Config.Cmd=[postgres]/Entrypoint=docker-entrypoint.sh，无命令行listen覆盖；RestartPolicy=no。bridge仅127.0.0.1:18435→5432，PGdata named volume exact，额外挂载旧backups→/backup只读，保留、不将合法原mount误判为目标测试隔离。API67821参数原scripts/a0v_current_preview_http.py --signed-receipt /Users/ddt/work/projects/ai_agent/.aos-current-build-pyGkqQ/signing-receipt.json --serve成立，Web67820原Vite路径成立。daily/web合法plist参数与此匹配，当前未注册，不擅自注册。旧watchdog/Prime脚本搜索未见8080/8434重启路径，这只覆盖已搜索脚本，需实际launchctl登记与automation到达语义再对账，不能宣称系统所有恢复器完全不存在。

维护执行器分阶段持久journal：preflight→intent→stop_clients→fence_tcp→snapshot_dump→independent_restore→migrate_steps→verify→restore_tcp→restart_clients→acceptance。每个变更记录attempt前置/实际postcondition，不存在done不得复做；故障最先只读调和。正式source资源Task独立于脚本开发Task。单次只支持135→142，不通用任意SQL；私有凭证只原bootstrap读取，本地docker socket维护不复制密码；shared evidence只有摘要/角色/版本/节点时间。

## 完整时序隔离验收补充

本轮在maintenance模块实现固定顺序journal（前步done才可下一步、每步attempt前持久、失败不写done、不进入后续、不自动恢复TCP/客户端）。随后完整isolated runner仅新nonce/test-only ctx，r4 archive/globals原样恢复→真实TCP baseline→关闭TCP实际重启→socket全备第二目标完整恢复→七步原Alembic迁移→592旧行与权限精确核对/Source增量与新角色空表→恢复监听重启→TCP/schema实际验收。完整时序不能只靠mock宣称通过，真实PG运行是本轮必需；当前源执行入口仍关闭，实际source独立Task/服务控制与最终浏览器合同继续待实现。

## 真实服务进程身份合同

文件仍scripts/a0v_current_142_maintenance.py和对应tests。将PID/PPID/UID/启动时间/完整argv SHA/cwd纳入精确指纹，必须完整argv等于已核实原plist固定向量（不靠substring命中），API/Web端口监听归属且单实例、没有子进程方可作叶服务候选；PID<=1/当前执行者/任何字段漂移拒绝。私有恢复参数独立记录，不输出全环境或密码；本切片只读取进程身份，不提供kill入口。ps快照不能消除检查与kill之间的PID竞态，真实控制尚须支持的进程句柄/所有权通道，未闭合不得宣称安全停机完成。累计合同测试+两个原真实leaf只读正向/错误参数拒绝证据。

实地进程guard正向失败揭示：Web67820有正常esbuild67827子进程，API无子进程；之前“两个leaf”假设须修正为API leaf+Web有固定受控helper，不是未知写者。只允许精确原esbuild executable/完整argv/父PID/启动时间/UID且无后代，其他children拒绝；Web停机须正常退出与helper自动退出实际验证，不对整棵任意进程树递归kill。身份合同通过仍不消除ps检查→signal竞态，当前源停机入口继续关闭。原拒绝日志事实保留，不能放宽为任意child可用。

下一实际Web正常退出验证仅新Popen拥有的隔离Vite实例，127.0.0.1:18434/strictPort，原8434不动；读取一个esbuild子进程身份，再仅terminate本轮Popen拥有的root，wait实际终止并核对helper是否自然退出，不向原进程/任意child发信号。端口如已占用拒绝，不kill已有监听。结果仅新实例正常退出机制，不授权当前WorkBuddy服务接管；若helper残留必须记录真实状态，不假定pid missing。

18434前置bind检查实际被占用，terminal1无启动/停止/杀进程。修订仅新probe使用OS分配的空闲loopback临时端口并strictPort，竞争占用则启动拒绝，不清理他人端口；不将端口检查失败当真实服务停止。

## 当前维护资源任务与监听恢复合同

实际源SHOW listen_addresses='*'，pg_settings source='configuration file'/pending_restart=false/version135；恢复不能仅改回有效值而遗漏postgresql.auto.conf原覆盖状态，应保存listen在pg_file_settings的原有效路径/值，以及是否已有auto覆盖（仅该GUC，不记录密码/其他配置），按原覆盖存在SET或RESET恢复后实测effective值和pending_restart。执行器每个变更前必须读authority和当前leases.json，并匹配原tasks Receipt、无Delivery、当前时间未到expiry、固定owner/revision；不能读旧status ACTIVE就认为授权有效。正式资源scope三个必需精确值为aos-platform/maintenance/current-preview-database、current-preview-api、current-preview-web（相同前缀）；与编码Task分离，无这些资源不得停止服务或DDL。此plan不创建正式源权限，完整执行器隔离验收后另登记资源任务。

## 当前入口施工合同（本轮）

复用相同完整时序，不另写缩水迁移路径：run_current固定source context/container/volume/数据库，无调用方任意资源替换，所有源命令及root SIGTERM前读正式Task/Lease；isolated入口仍不能选source。当前原全135摘要须与已完整恢复的r4一致，关闭TCP之后再取当前一致新全备/globals，第二新无网络目标完整恢复精确一致，才能七步原迁移。已验收metadata/role/ACL/序列校验不变。

维护两个原root：先保存并复核完整现存指纹与plist固定参数，最后再读一次，仅给原API/Web root一次SIGTERM，不kill父WorkBuddy/递归kill/helper或SIGKILL；按实际进程与监听回读停止及helper自然退出。用户已明确授权当前迁移/重启，使用标准窄作用域POSIX正常退出不额外索权；ps最后核验无法绝对原子保证PID，但不以缺理想句柄无限重复隔离准备。PID消失/漂移或未知信号结果只读对账，不重复信号。恢复只用已核实固定argv/cwd与允许的VITE_AOS_API_PROXY_TARGET，禁止复制全进程环境/密码；API原startup FLAGS保持Host/workers全禁。当前资源Task独立登记、签名原Receipt预检恢复后code/schema必须142，实际HTTP仅只读health/前台页，不称首链。停机后失败保留journal和备份，禁止自动恢复尚未核验的迁移中数据库。
