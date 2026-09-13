# 登记本地主库迁移与独立身份验证｜2026-09-13

基线920f425b。第1/6复核主库025、无登记表、路由0及专用Lease。第2/6写固定部署方案/执行器与证明保护测试。第3/6保留0600完整备份、恢复独立clone后026～030升级；指纹相同。第4/6验证FORCE RLS、只读Receipt ACL、三受限函数及反向角色无执行权；真实Owner/CurrentControlPermission正向由既有runtime-owner admin读取，默认user:dev(owner)及负租户拒绝，没有改成员。第5/6主库按相同指纹和版本应用026～030成功，业务行指纹不变；主库专用连接同样通过实际权限读取。第6/6代码提交后受控API重启/HTTP及浏览器回读另附运行证据；此文不提前宣称新API已上线。

主库aos_meta_head和clone aos_registration_20260913_test均a0v_030。准备、apply intent、apply证明保存在私有state目录。两个回执表为空，路由0，无业务请求/模型调用。专用登录非super/bypass/owner、NOINHERIT，只持有runtime和maintainer两角色；主/clone身份文件0600，不提交不展示内容。旧诊断Web metadata仍高权限，不与新登记连接混用，不能据此宣称整个Web身份已完成隔离。

真实发现：默认开发账号持久owner不属于安装控制角色，正确拒绝；没有为通过而赋权。首次主身份回读后落证明路径误指clone，被FileExistsError挡住，原证明保留。针对性RED后修复proof_name并重读成功，未重新生成凭据或重复迁移。程序apply遇到已有intent拒绝自动重试。

测试：执行器/启动器/连接器首轮28通过、7个PG测试当时跳过，后独立启用PG补跑连接器测试；对应日志/tmp/a0v-registration-deploy-final-tests.log与/tmp/a0v-registration-connection-pg-final.log。启动前检查CONTROLLED_API_LOCAL_DIAGNOSTIC_PREFLIGHT_GREEN。后续默认浏览器应403，不应假装未登记。真实首链、八场景、连续观察仍未完成。

备份校验：5190796 bytes，sha256:f2ef3dab27525666630505bdf76da7fe4b41beb7f39d26a10a252f0b9b4cded0；指纹覆盖15个既有关系。
