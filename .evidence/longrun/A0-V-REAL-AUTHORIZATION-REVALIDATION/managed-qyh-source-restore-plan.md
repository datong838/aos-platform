# AOS托管栖月汇数据源恢复

基线15693cd9，原SSH/DB只读探针已成功。通过正式POST /v1/sources登记niushop-qyh、jdbc-mysql-ssh、runtimeMode direct，配置来自原栖月汇电商多平台.env，在内存中向本地API提交，不输出配置正文。先读source列表确认缺失，保存后按返回configurationRevision执行正式/test探针；不手工SQL写meta_source，不调用伪同步facade，不执行源业务写入。

登记前最小修复jdbc_connector_runtime.py的密码helper：使用shlex.quote和printf '%s'避免单引号/命令替换被执行，文件仍0700、现有清理路径不变；密码SSH路径StrictHostKeyChecking改yes，使用刚刚验证过的known_hosts。私钥路径本波不改。测试test_jdbc_askpass_integrity.py通过本地helper验证特殊字符原样输出、不产生测试marker、权限和清理、SSH参数启用主机校验；无网络。随后相关连接/探针回归，定向重载API（独立运行宿主不停），执行真实Source Owner和只读表目录探针。

公开API/证据只记录sourceId、版本、状态和目录数量，不记录密码/端点/业务正文。现有数据源Owner将执行配置保存在私有props，此机制不是生产Secret Manager；上线前仍须完成正式凭据引用存储。当前本地开发沿现有合同恢复，不伪称凭据治理已完成。
