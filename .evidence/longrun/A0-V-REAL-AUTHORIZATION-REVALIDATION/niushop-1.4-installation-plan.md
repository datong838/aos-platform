# Niushop 1.4 新安装恢复

2026-09-12，2a71f3f7；前序a0fd8e25已正常uninstalled@6。新注册根12版本，Niushop1.4已published，尚无新安装。

文件清单：scripts/a0v_ecommerce_schema_receipts.py 新增互斥niushop-1-4固定profile选择，复用新私有注册后继；schemas验证先物理只读，再apply_once记录新包要求，不运行DDL。scripts/a0v_ecommerce_1_7_first_install.py 提取固定installation_target，新增互斥niushop-1-4，STATE=state/niushop-1.4-first-install.json、key prefix=a0v-niushop-1.4、adapter1.4/core1.3/growth1.7，明确前序a0fd8e25已退役。原3路径不变。tests/extension_runtime/test_ecommerce_schema_receipts.py及新test_niushop_1_4_installation_target.py覆盖固定版本/根/前序/命名空间与互斥；旧正式首装tests保持。

后续配置与持续性入口同样新增互斥profile：scripts/a0v_ecommerce_1_7_configure.py的setup/target/run选择新根和新state、拒绝历史UUID；scripts/a0v_ecommerce_continuity_observe.py显式观察新state，不改默认。测试test_a0v_recovered_configuration_target.py更新对应目标。先完成schema/安装入口，再配置观察段；不混用旧实例审批或租约。

顺序：提交并验证入口→真实物理schema预检→正常schema回执→新组合create/submit/approve→停止唯一旧Host并新根启动→apply一次→只读等待applied→verify一次→active→四来源stage/configure/enable。每个命令已存在则只observe，不换key重试unknown；可恢复失败沿原reset Owner，不手写状态。新Host观察时仅以随进程退出的本地抑制空闲休眠保持测试连续，不修改系统永久电源设置；不能抵消手动合盖或低电量。

完成标准：新lock只选Niushop1.4，实际3资源/精确注册，verify和配置/启用事件提交，canary0，跨初始deadline续租；发布与安装不是源读取授权。P01仍禁用，源claim占用/单次读取尚待接线，主库a0v_023，230L0挂起、不push。

入口第一段：3 RED/3 passed后schema/安装/原canonical首装相关14通过；补充前序仍active时不得调用create的负例，目标文件3通过。13:43:37Z真实物理预检通过，三个包各13项关系与实际已安装Alembic祖先匹配，未记录schema receipt；见niushop-1.4-schema-preflight.json。新profile已由CLI测试证明传入adapter1.4及精确前序，原三个state/key保持，配置与观察入口尚待下一段。
