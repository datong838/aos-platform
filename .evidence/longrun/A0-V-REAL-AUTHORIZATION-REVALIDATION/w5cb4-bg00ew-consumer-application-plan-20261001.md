# BG00EW API消费者应用适配

基线AOS-001011/m1@84401023；复习231首链依赖、BG00EM持久attempt与外部身份、BG00EV客户端unknown边界。不改当前实例，正式跨UID部署/签名配置/118→122迁移独立门。

文件：contracts.py抽出NetworkConsumerReferences（schema、Proposal/Event与3hash），原Command/Inquiry继承并保留scope/token及全部验证；新增aip_network_consumer_application.py与tests/aip/test_network_consumer_application.py；现有routers/aip_runtime_guard_policies.py新增消费/只读对账POST入口；plan/verification精确登记。

应用配置由server app.state持有typed ConsumerApplicationConfig(endpoint,api_attempt_directory)，默认None→503，不接受body路径/角色/凭据。body仅References，scope取已验证Principal，token来自Authorization经parse_bearer；应用再次复用authenticate_consumer_request并比较subject/scope/token_kind，防stale依赖或混合身份。服务端仍逐次重验。

消费前复用已有reserve_consumer_attempt于API自有0700目录，固定Proposal key；API目录须与消费者私有目录分离（OS所有者不同），不复制状态机。首次才能发Command；Already/Unknown一律发Inquiry；Conflict拒绝。发送前连接失败也不自动重发，后续只读对账，保守冻结。Inquiry不创建attempt。结果只传既有有限状态/历史Receipt，不称激活。无自动回调/重试。

路由 /networks/activation-consumptions 与 /networks/activation-consumptions/inquiry，依赖require_principal+server config；应用固定错误码，未知202、observed200、conflict409、blocked403、未配置503。默认禁入旧路由不变。HTTP payload使用typed引用避免scope/token注入。

测试：真实临时TLS签名身份+私有文件验证认证与一发后查询；IPC仅用受控捕获替身验证路由分派，明确不作正式业务验收。默认HTTP503、额外字段422、真实401/403身份拒绝、持久文件不含token。复用既有client/socket/签名PG及runtime guard API相邻回归。无UI改变，浏览器不适用。精确m1提交/AOS-Prime同步，不push。

## 回归定位修订
累计session97572：58 passed/10 failed，其中HTTP字段拒绝按仓库handler应为400而非方案草案422；9项签名PG失败由通用client fixture删除meta_object_type正式元数据引发。新测试改独立FastAPI实例+真实require_principal/错误handler，仅在隔离PG建org-org工作区，不运行通用client清理，不放宽生产对象门。应用attempt路径要求绝对路径；仍复用原私有目录门。
