# BG00EZ 签发API产品通道与持久记录计划

基线AOS-001014/m1@5a1403c7；复习231/407、issuer auth/attempt/contracts/client及consumer application/startup。Task W5CB4-BG00EZ-20261001；本波不改当前真实实例、库或身份材料。

## 方案与文件
- aip_private_dispatch.py：从consumer application提取先持久记录再单次发送、重复/未知仅inquiry、发送异常返回unresolved的共有流程；不复制安全状态机。
- aip_network_consumer_application.py：复用上述流程，保留既有HTTP/错误合同。
- aip_network_issuer_application.py：私有API配置及execute_issuer；租户/actor来自认证Principal，Bearer重新验证并比对Principal；复用reserve_decision_attempt。冲突409，存储错误503，身份403；inquiry绝不reserve。
- routers/aip_runtime_guard_policies.py：新增POST networks/activation-proposals/{proposal_id}/decision-attempts与其/inquiry，使用原DecideActionProposalRequest及Idempotency-Key。返回事件对账状态200/202/409/403；缺配置503。原decision的ActionDraftBundle合同不变，不另造审批权威。查询携带原决定仅计算request_hash，不执行决定。
- aip_network_issuer_startup.py与main.py：AOS_NETWORK_ISSUER_API_CONFIG私有JSON，字段schemaVersion/socketPath/apiUid/issuerUid/ipcGid/apiAttemptDirectory；复用现有私有读取。缺失None，错误启动拒绝，业务body前加载，退出清空。无socket/DB连接或身份创建。
- tests/aip/test_network_issuer_application.py、test_network_issuer_startup.py：真实临时私有文件、TLS/JWT/HTTP；捕获IPC只证分发逻辑，不冒充签发验收。

## 必须验证
RED缺模块；首次Command/重复Inquiry/显式Inquiry；进程重建读取既有记录；坏身份不写记录不发送；冲突不发送；破损记录仅查询；发送异常不得重发；HTTP身份字段注入拒绝；默认503；配置权限与生命周期fail closed。累计复验消费者共享流程与issuer协议。无UI改动，浏览器不适用。

## 风险、部署与回滚
API与issuer各自持有独立目录与身份；记录仅防重不授权。Response observed只代表既有签发服务的Event对账，非激活/首链。外部OIDC、OS身份、119–122部署、启动载体修复保持独立门。代码回滚仅精确本波文件，不删除attempt记录；当前库只读，旧Run/manual run_definition/商城源/Provider均不触碰。不push。
