# BG00GB 预算消费产品请求与原请求恢复计划

基线AOS-001042/42a3525c/a0v127。复习231-5审批费用/unknown恢复、435、FV预算费用签发product/client及FZ/GA消费。7强一致CURRENT。本波不迁移/重启真实库、不启Host/worker/Provider，无商城源/旧Run/手工Run。

## 文件及合同
- aip_private_product_request.py：抽取cost product现有私有文件保存/竞争处理/冲突/原请求恢复/一次dispatch流程，回调仅领域envelope/command/读原body/send，保持老接口错误码。aip_budget_cost_product.py委托此公共流程，旧审核业务不变。
- aip_private_service_transport.py：复用endpoint身份/Unix内核peer，抽取现有单帧发送/只一次读响应的纯传输。aip_budget_cost_client.py委托、原响应校验不变。
- aip_budget_consumer_client.py：固定consumer Endpoint，exact schema/status/receipt字段、proposal/hash/decision/requestDigest一致，拒绝activationEligible=true与未知字段；不自动重试，unknown回查由产品原请求链处理。
- aip_budget_consumer_product.py：API配置AOS_BUDGET_CONSUMER_API_CONFIG，私有exact socketPath/apiUid/consumerUid/ipcGid/requestDirectory，无DB或user参数。body仅proposalHash/decisionId，scope+actor由重新认证及当前成员解析；当前原maker且原approved关联复核，before首次slot拒绝已撤销/过期批准；GET已尝试历史允许原Receipt对账。稳定slot按tenant/actor/proposal，不随body变化；只fresh且fsync完成文件可execute_once，其余只inquiry。保存body/hash不保存JWT。
- routers/aip_budgets.py：POST/GET /cost-proposals/{proposal_id}/consumption-request，服务端持久key、不接受调用者key/actor/租户。no-store，observed200/not_attempted200/unresolved202/conflict409/blocked503。
- tests/aip/test_budget_consumer_product_pg.py：真实HTTP/PG/JWT批准/消费，适配器仅代替跨UID传输（不算正式跨UID证明）；刷新/重复/并发/changedbody/fsync/损坏slot/身份错配、unknown前后commit不重发。
- tests/aip/test_budget_consumer_client.py：真实socketpair单帧/回执丢失/精确response校验、真实sameUID peer拒绝；不以测试响应当正式业务。

## 验证与后续
RED→专项+cost product/client/FZ/GA相邻累计→复审verification/精确提交/Delivery/CAS/436/D-waves。无前端变更、正式API不重载，浏览器产品验收待下一UI波。下一BG00GC接Capacity UI批准预算消费与刷新恢复，合法development价格/预算政策producer及实际Task风险联合证明继续。正式不同UID/最新实例127恢复仍独立身份/一致备份/克隆/零窗口波。
