# 真实数据源配置端到端施工方案

基线25c400c4；目标是用户安装后能配置真实连接并自然进入数据链，不以登记元数据替代可执行连接。m1串行，无新批准要求，230 L0与不push规则保持。

## 已核查的实际断点

1. DataSourceCreatePage.handleCreate发送type/config/tables但不发id；wave_ext.ConnectorIn只接收必需id/type/runtimeMode。因此当前向导与Owner合同不一致，config不会成为可执行配置。
2. 向导handleTest调用/v1/sources/test；API Python源码搜索未找到该路由。成功页面还以临时生成id填补服务端缺失id，不能作为登记证据。
3. 既有data_os_store.persist_source会持久化非元数据字段到meta_source.props；ar2_010的data_source_configuration_revision及SourceConfigurationRevisionStore提供配置版本，不应建立第二套配置数据库。
4. ec_source_adapter必须从当前tenant meta_source取props。真实选用jdbc-mysql-ssh，插件manifest含sshHost/sshUser/dbHost/database/username及两组认证方式。JdbcConnectorRuntime支持这些键；secretRef/sshKeyRef的vault实现目前是本地文件占位，不能宣称真实Vault已接入。
5. 前轮修复只保证元数据登记持久成功，没有补齐配置或测试连接。恢复库真实连接缺失的用户位置问题仍等待回复，不能复制dev-org配置。

## 实现合同与顺序

A. 先补严格的连接配置解析：复用已安装插件身份，对jdbc-mysql-ssh的受支持字段明确白名单、端口类型范围、必需项、SSH与数据库认证二选一；未知字段及相互冲突拒绝。凭据不在repr、日志、响应、Receipt中出现，不把连接参数混入运行节点或浏览器存储。已有无config的纯元数据登记兼容；带config必须完整校验。

B. 扩展现有登记Owner接收config并形成适配器认可的props（connector_type等路由字段由服务器决定，客户端不得伪造tenant/status）。使用已存在meta_source及版本触发器，保存成功后才更新缓存，公开响应仅白名单元数据并给出真实id。向导必须生成/提交一个稳定登记id并验证响应id，不用假成功fallback。暂不复制连接器引擎的内存Source作为权威。

C. 测试连接必须针对已保存、当前tenant的sourceId与exact配置版本执行，走固定只读探针，超时脱敏返回；不得让客户端任意SQL/连接串绕过Source Owner。能力只表示连接可达，不能升级为数据新鲜度、履约或业务完成。失败/未知不自动触发接入。真实测试前核对既有连接器隧道缓存tenant与配置版本隔离，避免凭据变更后复用旧连接。

D. 向导流程对齐：配置保存→测试已保存连接→实际schema/表选择→只读有界抽取及规范化；不使用假表数/假成功。字段输入以插件支持项展示，SSH认证与DB认证分清。新增接口须验证principal租户和配置权限；沿用现有认证合同，不在前端发明权限。

E. 数据链：恢复当前渠道/实体绑定，执行已存在规范化入口；验证Product等实际对象和exact payload hash，再在选定事实边界生成Evidence正文与Bundle，保留cutoff/来源/许可。SourceReadObservation/QualityEvidence不冒充事实覆盖。

## 文件与验证

预计后端：aos_api/routers/wave_ext.py、独立source_connection_config.py（纯合同解析）、既有data_os_store及ec_source_adapter调用组合；前端apps/web/src/pages/s2/DataSourceCreatePage.tsx及专项测试。只有经实证需要时才改存储，不创建新schema。

先针对纯合同和接口匹配做故障测试，再PG配置版本/租户隔离与脱敏，随后浏览器端完整向导，最后真实连接/抽取验证。无真实配置时继续A/B与测试，不能填造凭据。未知提交先回读，成功提交前不启动连接。每步留证据提交。

本方案基于源码检查，尚未实现A-E，不是完成声明。完整经营首链、八工作台、连续观察、发布评估仍待完成。
