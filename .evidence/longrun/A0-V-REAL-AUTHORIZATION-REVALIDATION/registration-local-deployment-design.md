# 登记服务本地主库部署方案｜2026-09-13

基线920f425b。只操作colima-aos-extension/aos-a0v-recovery-pg内aos_meta_head，当前a0v_025、dispatch=0；026/029两回执表不存在。runtime与maintainer均NOLOGIN/NOSUPERUSER/NOBYPASSRLS/NOINHERIT，专用登记登录不存在。现有Web metadata诊断super连接不用于登记Owner。

第1/6核对基线与专项Lease；第2/6固定方案及执行器；第3/6保留0600 pg_dump并恢复至独立命名clone，026～030按原Alembic链升级，比较安装/配置/业务路由/任务数据指纹；第4/6在clone检查新表RLS、immutable权限、027/028/030函数ACL及读路径；第5/6在主库相同基线/CAS/文件hash和备份校验后执行增量迁移，再比较指纹；第6/6建立或验证专用无特权身份，配置现有固定连接器并重启受控API，验证当前状态读取；下一波实际首登记前置与自然链。

新增scripts/a0v_registration_deploy.py及针对性测试；状态目录../.aos-recovery-20260913/state/registration-deployment，clone aos_registration_20260913_test。命令prepare先完成备份/恢复/迁移证明，apply只消费固定证明。备份、clone和失败阶段都保留，不覆盖已有准备，不删旧数据库。文件hash绑定026～030，两个新回执表初始为空；028撤销runtime直接dispatch DML，只保留SELECT和受限行锁。升级事务不插入登记、不激活路由、不改预算、不调用模型/商城。指纹包含安装及revision、runtime配置、业务调度/command/Case等实际存在关系；变化需要复核，不能自动重试覆盖证据。

身份准备与API接线另一个子步骤，迁移证明先完成。专用登录NOINHERIT/非super/bypass/createrole/createdb/replication，恰好两角色membership，无admin option；凭据只写0600固定身份文件，禁止命令参数/日志/提交出现密码DSN。当前真实权限及租户仍由Owner校验，配置成功不等于业务开启。主库部署后不执行降级删除回执表；异常保留备份和证据，先诊断，必要恢复须精确核对当前变更，不能覆盖业务数据。


独立恢复库已完成026～030，数据指纹一致、RLS/ACL通过。主库apply前新增identity-clone检查：创建唯一aos_ecommerce_registration_control登录，仅两角色membership且无管理选项，首先只生成指向clone的0600身份文件。生产registration_connection与真实CurrentControlPermission读取当前97aeb2e7安装，验证user:dev当前成员，负租户拒绝。不得伪造成员或放宽权限以做绿。已有身份文件只校验复用，绝不覆盖密码；首次失败保留文件和角色。主库迁移后再写独立main身份文件并配置API，不把clone DSN接入主运行服务。


真实权限复核纠正：user:dev持久角色owner不在冻结安装控制角色集合，因此克隆检查正确拒绝；不改成员或扩大角色集合。正向改用已有a0v-ecommerce-growth-1.4-runtime-owner（持久admin），再要求默认user:dev与dev-org负租户都被拒绝。主库apply前重新运行同一identity-clone只读验证，不只信旧证明。当前默认浏览器身份尚不能操作登记，后续应走既有正式角色/身份配置路径，不能把token内admin列表替代持久授权。
