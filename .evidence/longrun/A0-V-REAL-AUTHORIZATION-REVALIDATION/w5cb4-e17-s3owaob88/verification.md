# b88 原来源许可请求与独立原审批验收

基线 m1 f7739544；authority AOS-001329；唯一施工写者，当前135真库只读。此交付完成原Proposal/Approval代码与隔离验收，不完成来源许可发行、八实际依赖或自然经营首链。

## 方案与代码复审
严格DTO完整绑定原source/provenance request hash、安装/ETag/revision、release三个摘要、签名Policy、明确许可用途、权利声明和三个时间窗口。复用原canonical hash、build provenance/Receipt、installation/Registry revalidator、原AipActionStore请求锁、不可变draft完整信封、审批key/CAS/checker.1/eligibility。maker与checker当前PG Owner共同锁，checker独立actor；专用session=current身份无成员/高权，自身RLS，SERIAL与固定schema/timeout；外部JWT先签名/issuer/audience/expiry/tenant验证，后专用SCRAM连接。没有影子Approval/LicensePolicy，没有赋予通用执行器消费权。

a140冻结原metadata及Source Proposal条款，独立批准角色保留NOLOGIN。a141仅9个UPDATE列、原审批/动作事件INSERT、作用域只读及原中性初始化锁EXEC；Owner/安装/两metadata的锁列权限实际DML全部拒；原Proposal/draft只走合法状态迁移，批准须原绑定事件。无issuance/head/RegistryReceipt写权，未供给生产LOGIN或凭据。

## 实际验证
- 最终相邻十一模块：159 passed / 7 warnings / 86.99s，green-complete-approval-cumulative-r3.log。包含请求合同、metadata/权限/真实RSA签名拒绝、源身份与执行禁入、原Policy/guard/原Action执行回归。此前首个累计文件名错误退出4未执行；r2为夹具百分号参数错误1failed/158passed/86.77s，均保留，不计GREEN。
- 最新实际签名1.13.0/完整schema141：1 passed / 7 warnings / 21.59s，green-signed-approval-schema-final.log。实际原Store build+provenance、RSA签名/JWKS验证、真实独立SCRAM登录、原Proposal批准与同key回放/跨事务adapter回放；唯一批准事件的原actor/slot/version/hash/policy/eligibility一致。JWKS网络传输为隔离字节fixture，未替换签名/claims验证；测试Owner与LOGIN不是生产IdP或业务权利供给。
- 真实四writer PID图：maker/checker Owner删除、installation写锁、READ COMMITTED raw revoke均等待独立批准事务；writer全部rollback。真实Owner移除后回放拒、canary原Proposal/Approval读0、同人/admin/缺Owner/version/hash拒。原Store合法撤回与实际等待DB clock到期均批准0。批准前/后schema漂移、草稿/hash内容不一致、不同actor重放、状态重置及普通metadata修改拒。
- 十文件编译通过；已有修改精确diff通过。无页面改动，浏览器验收不适用。
- 所有pytest handle终态；测试数据库49保留，两本轮临时角色安全attrs/双向成员0/共享依赖0核验后删除，剩余0；不DROP OWNED历史、不清旧测试库。

## RED与排障保留
metadata初始6failed；来源条款改标签1failed/19passed；独立ACL r2三个缺权限/检查器RED；草稿直接approved真实RED；原immutable draft purpose与row不一致真实RED；不同Owner同key回放真实RED（未新增事件）；原状态重置真实RED；普通metadata UPDATE(id)两项真实RED；schema优先级漂移真实RED（未证明临时表成功越权）。RLS隐藏记录由原a0v118保护拒，初版regex/cleanup失败不是越权。独立安装共享锁需要UPDATE USING policy，增加exactscope policy后仍用trigger禁止实际DML；事件actor字段及已开事务重复设isolation是夹具错误，未放宽生产合同。

## 风险与下一入口
当前正式外部IdP/Owner权利与专用凭据仍未供给；无生产公开路由/启用。私有事务服务需要调用者立即提交；时间授权仍由后续消费边界live clock复核。完整来源发行需独立issuer重新消费当前Owner/原批准、当前源/Policy/安装、初始化独占锁，原子issuance/head/RegistryReceipt与竞争/幂等/失败rollback；下一b89。此代码不启动Host/worker/Provider、商城源、旧Run或外部效果；当前135不迁移/重启，不push、不改其他分支，用户九M保护。

Prime LaunchAgent pid1844/status0；memory health snapshot observed07:04:35 authority1329 GREEN_WITH_WARNINGS，daemon.sock未发现，不把socket缺失或投影CURRENT称完整服务/模型验收。无新增真实模型调用，保留agnes r3 assessment6/7/O4限制。Goal active，真实09提醒到达及自然首链仍待真实证据。
