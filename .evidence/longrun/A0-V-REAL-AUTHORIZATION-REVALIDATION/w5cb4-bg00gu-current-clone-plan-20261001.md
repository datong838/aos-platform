# BG00GU 当日当前库备份与最新代码克隆恢复演练

基线m1 e8d699bf/AOS-001061。独立于待裁决BG00GT模型评测授权；依据用户每日最新代码重启门、231-4及BG00dl/BG00bu备份克隆方案。当前真实库仍只读，本波不切换或重启当前实例。

## 实测与范围

当前colima-aos-extension/aos-a0v-recovery-pg挂载aos-a0v-recovery-pg-data；只读SQL回读aos_current_preview_20260927/aos_app/a0v_118、runtime_binding=0、host_assignment=0。代码迁移头a0v_130，现启动器仍显式期待118，故不能直接启动后声称最新。8080/8434监听、18181未监听。

复用隔离colima-aos-a0v-test-only/aos-bg00dl-isolated-pg（回环18440、管理员bg00dl_admin），已有旧118恢复库保留；当前无其他client backend。在其中新建唯一aos_bg00gu_current_20261001，禁止覆盖既存库；不更改旧库业务记录。新备份与状态放aos-recovery/.aos-current-backup-20261001-bg00gu（0700/文件0600），不再占父目录。

## 执行步骤与验证

1. 核m1/当前HEAD、七strong CURRENT与validate GREEN、卷与数据库身份。使用现有bootstrap连接参数读取器，仅进程内连接、日志不输出凭据。
2. 源库REPEATABLE READ READ ONLY，固定控制面表计算count/行hash摘要并export snapshot；pg_dump -Fc --snapshot作一致备份，保留dump SHA256、权限、TOC；另存不含口令的globals仅作恢复材料，不自动覆盖隔离角色。
3. 精确检查目标context/container/loopback/database不存在、集群无其他客户连接。新库template0、REVOKE PUBLIC CONNECT；pg_restore --exit-on-error，失败保留现场、不重跑。核源与克隆118及所有原public表数量/行数摘要，固定控制面再核行hash。
4. 从最新代码Alembic ScriptDirectory确认118→119…130单头线性链，使用程序化Alembic已提供连接，只连新clone（不改source连接白名单、不读取商城源、不启任何worker）。记录逐步迁移版本与结果；旧表行数及控制面摘要应不变，alembic_version单独核130。
5. clone只读检查新消费者/签发角色默认NOLOGIN、关键表/函数与禁入触发器存在、正租户安装状态保留，source仍118/绑定与Host0。实际业务首链与正式不同身份消费者不由此证明。
6. 完整记录失败、命令/退出码/摘要、verification与精确提交，AOS/Prime/续接/D-waves更新。后续另波才评估零执行窗口、第二份停机备份、当前迁移和完整重启；不把此次克隆演练当今日重启门完成。

## 文件与风险

只提交本plan与verification；一次性执行脚本和私有数据库备份留在上述0700恢复目录便于复核。没有生产代码改动或新接口，浏览器不适用。迁移可能因真实历史权限/元数据不同于空测试库而失败，必须保留失败并定位最小点，不关闭migration guard、不重置角色、不stamp版本。

源只读不会删除库/卷/备份；克隆管理员只用于隔离恢复迁移，不用于伪造批准、Run、Receipt或业务验收。旧12Run、不读商城源、230L0挂起、无Provider/Host/worker与unknown重发边界保持。

迁移源码复审补充：129/130按方案向meta_object_type/meta_action_type分别新增3项固定策略元数据，因此升级后旧表计数只允许这两表各+3；原行内容必须保留，其余旧表计数保持，alembic版本值单独验证。克隆DDL用aos_app表owner身份执行（仅隔离恢复），避免管理员身份不匹配元数据保护；不以该管理员身份执行任何批准或消费函数。
