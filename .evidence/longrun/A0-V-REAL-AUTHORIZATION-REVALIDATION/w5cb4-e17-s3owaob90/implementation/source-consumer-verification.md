# 完整Task内部原来源消费实证

原完整签名安装/Owner Proposal/实际OIDC批准及签发 baseline1passed/32.08s；首次路径写入错误导致该轮没有消费hook，日志已明确改名pre-hook-baseline，不作为RED。补hook后真实RED为read_formal_license_source_facts ImportError，1failed，保留source-consumer-red.log。

最小实施：原审批信封、锁定metadata、批准Proposal/event及非秘密签发request hash抽取私有共享函数；原maker/issuer身份、批准/签发写入及hash表达式保留。AST原envelope/metadata/Proposal-event等价读回source-original-extraction-review.json。正式evaluator真实native/SCRAM/SERIAL/双身份/固定tenant及超时、search_path检查统一原连接校验，Health复用，无fake Principal/token/callback。

原来源批量消费者先发现原exact授权，再预锁全部Proposal和批准→所有Owner→安装→Source init/head共享→原Registry证据和签名Policy→原metadata/draft/Receipt；锁后重新核验发现值。校验当前两Owner、active安装/version/etag、完整授权schema和用途、原approvedProposal/唯一event/eligibility、原draft及哈希、无withdrawal、BuildProvenance、签名policy、原source_license.issue Receipt及原request hash/result/时间；数据库clock取最小期限。只返回事实，没有新许可、批准、Hold、预留、binding或proof写入及启动权。

实际signed r1 1passed/34.45s；新增正负及原三写a144机制hook后最终1passed/7warnings/32.60s，见signed-final.log及source-consumer-facts.json：5433一次性aos_test_714ca8ad673c_ti4_test，原许可1/Receipt2/proof0消费前后不变。十类错误拒绝：错hash、安装版本/etag、bool etag、重复ref、canary GUC、两Owner分别降为admin、legacy schema、wrong original Receipt。三个实际原writer Owner/安装/Source revoke在native evaluator锁上阻挡，释放后rollback。故障维护插入2条不可变legacy行仅用于负向，该库最终许可3/Receipt2/proof0，原head已恢复；不能把故障注入行计为消费者许可效果或业务正向。测试角色恢复NOLOGIN/PASSWORD NULL，没有DROP OWNED。

累计r2 178passed/1strictxfail，但签名fixture同进程因先行Registry测试创建两额外安装在原count==1前提失败，尚未进入新consumer；保留日志，不改弱断言。最终拆开新的独立测试库：相邻178passed/1strictxfail/7warnings/23.09s + signed1passed/32.60s。相邻覆盖原Source请求/批准/issuer、Action Draft/Proposal/Approval、Health fence/ModelRuntime与formal ACL/transport。唯一strictxfail仍完整evaluate_binding_in_transaction缺失，未删弱。

当前142没有迁移/写入，Host/worker/Provider/商城源/旧Run/manual/外部效果未发生，无新真实模型调用。原九项用户修改保护。后端无UI改变，浏览器不适用。

范围限制：当前signed消费仅一个Source；多Source真实批量、消费侧独立过期/withdrawal/合法狭窄用途许可拒绝仍待完整命令验收，未把原issuer的相关测试升级为consumer独立通过。完整八事实/全部Resolver候选/预算/同事务Receipt-CAS-proof/API尚未实现，完整Task ACTIVE/整体pending/原last GREEN保持；本段不是b90 Delivery或自然首链完成。后继直接接完整组合，禁止以独立reader成功缩小完整退出。
